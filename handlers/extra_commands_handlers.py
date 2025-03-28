import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from handlers.conversation_handlers import send_thumbnail_photo
from handlers.common_handlers import check_for_cancel
from utils.yt_helpers import (
    is_valid_youtube_url_format,
    get_youtube_url_type,
    get_youtube_url_id,
    get_videos_urls,
    get_hidden_playlist_videos,
    get_video_infos,
    get_playlist_infos,
)
from utils.bot_data import VIDEO_OPTIONS, PLAYLIST_OPTIONS
from utils.format_helpers import format_infos


async def get_send_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered by /info command, send information on the video or playlist to user."""
    context.user_data["conversation"] = False
    stop_event = asyncio.Event()
    check_task = asyncio.create_task(check_for_cancel(update, context, stop_event))

    if not context.args:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Please provide a YouTube video or playlist URL."
            "\nExample: /info <URL>",
        )
        return

    url = context.args[0]

    if not is_valid_youtube_url_format(url):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Invalid YouTube URL format. Please send a valid video or playlist URL.",
        )
        return

    if not (
        (url_type := get_youtube_url_type(url))
        and (url_id := get_youtube_url_id(url, url_type))
    ):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Invalid YouTube URL. Please send a valid video or playlist URL.",
        )
        return

    if stop_event.is_set():
        return

    if not (videos_urls := await get_videos_urls(url_type, url_id)):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Unavailable YouTube URL. Please send a valid video or playlist URL.",
        )
        return

    processing_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"🔍 Fetching {url_type} informations... Please wait.",
    )

    if stop_event.is_set():
        return

    if url_type == "video":
        infos = await get_video_infos(videos_urls[0])
        options = VIDEO_OPTIONS
    else:
        infos = await get_playlist_infos(url_id)
        options = PLAYLIST_OPTIONS
        if hidden_videos := await get_hidden_playlist_videos(videos_urls, stop_event):
            infos["playlist hidden videos"] = hidden_videos
            options.append("playlist hidden videos")

    if stop_event.is_set():
        return

    message = format_infos(infos, options)

    await context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=processing_message.message_id,
    )

    if stop_event.is_set():
        return

    if infos.get("thumbnail"):
        if await send_thumbnail_photo(update, context, infos["thumbnail"], message):
            return

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
        disable_notification=True,
    )

    check_task.cancel()


async def get_send_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered by /thumbnail command, send video thumbnail to the user."""
    if not context.args:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Please provide a YouTube video URL." "\nExample: /info <URL>",
        )
        return

    url = context.args[0]

    if not is_valid_youtube_url_format(url):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Invalid YouTube URL format. Please send a valid video URL.",
        )
        return

    if not (
        (url_type := get_youtube_url_type(url))
        and (url_id := get_youtube_url_id(url, url_type))
    ):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Invalid YouTube URL. Please send a valid video or playlist URL.",
        )
        return

    if not url_type == "video":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: This is a playlist URL. Please send a video URL.",
        )
        return

    if not (videos_urls := await get_videos_urls(url_type, url_id)):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Unavailable YouTube URL. Please send a valid video URL.",
        )
        return

    infos = await get_video_infos(videos_urls[0])

    if not infos.get("thumbnail"):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Thumbnail not found for this video.",
        )
        return

    message = format_infos(infos, ["thumbnail"])

    if await send_thumbnail_photo(update, context, infos["thumbnail"], message):
        return

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
        disable_notification=True,
    )

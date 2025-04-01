import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from handlers.common_handlers import check_for_cancel
from handlers.conversation_handlers import send_thumbnail_photo

from utils.bot_data import PLAYLIST_INFO_OPTIONS, VIDEO_INFO_OPTIONS
from utils.format_helpers import format_infos
from utils.yt_helpers import (
    get_hidden_playlist_videos,
    get_playlist_infos,
    get_video_infos,
    get_videos_urls,
    get_youtube_url_id,
    get_youtube_url_type,
    is_valid_youtube_url_format,
)


async def get_send_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered by /info command, send information on the video or playlist to user."""
    context.user_data["conversation"] = False
    cancel_event = asyncio.Event()
    check_cancel_task = asyncio.create_task(
        check_for_cancel(update, context, cancel_event)
    )

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
            text="❌ Invalid YouTube URL format. Please send a valid video or playlist URL.",
        )
        return

    if not (
        (url_type := get_youtube_url_type(url))
        and (url_id := get_youtube_url_id(url, url_type))
    ):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Invalid YouTube URL. Please send a valid video or playlist URL.",
        )
        return

    if cancel_event.is_set():
        return

    if not (videos_urls := await get_videos_urls(url_type, url_id)):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Unavailable YouTube URL. Please send a valid video or playlist URL.",
        )
        return

    processing_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"🔍 Fetching {url_type} informations... Please wait.",
    )

    if cancel_event.is_set():
        return

    if url_type == "video":
        infos = await get_video_infos(videos_urls[0])
        info_options = VIDEO_INFO_OPTIONS
    else:
        infos = await get_playlist_infos(url_id)
        info_options = PLAYLIST_INFO_OPTIONS
        if hidden_videos_urls := await get_hidden_playlist_videos(
            videos_urls, cancel_event
        ):
            infos["playlist hidden videos"] = hidden_videos_urls
            info_options.append("playlist hidden videos")

    if cancel_event.is_set():
        return

    infos_message = format_infos(infos, info_options)

    await context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=processing_message.message_id,
    )

    if cancel_event.is_set():
        return

    if infos.get("thumbnail"):
        if await send_thumbnail_photo(
            update, context, infos["thumbnail"], infos_message
        ):
            return

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=infos_message,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
        disable_notification=True,
    )

    check_cancel_task.cancel()


async def get_send_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered by /thumbnail command, send video thumbnail to the user."""
    context.user_data["conversation"] = False

    if not context.args:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Please provide a YouTube video URL." "\nExample: /thumbnail <URL>",
        )
        return

    url = context.args[0]

    if not is_valid_youtube_url_format(url):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Invalid YouTube URL format. Please send a valid video URL.",
        )
        return

    if not (
        (url_type := get_youtube_url_type(url))
        and (url_id := get_youtube_url_id(url, url_type))
    ):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Invalid YouTube URL. Please send a valid video URL.",
        )
        return

    if not url_type == "video":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ This is a playlist URL. Please send a video URL.",
        )
        return

    if not (videos_urls := await get_videos_urls(url_type, url_id)):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Unavailable YouTube URL. Please send a valid video URL.",
        )
        return

    infos = await get_video_infos(videos_urls[0])

    if not infos.get("thumbnail"):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Thumbnail not found for this video. Please try another one.",
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

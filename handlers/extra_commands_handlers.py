import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from handlers.common_handlers import (
    check_for_cancel,
    send_thumbnail_photo,
    validate_youtube_url,
)

from utils.bot_data import PLAYLIST_INFO_OPTIONS, VIDEO_INFO_OPTIONS
from utils.format_helpers import format_infos
from utils.yt_helpers import (
    get_hidden_playlist_videos,
    get_playlist_infos,
    get_video_infos,
)


async def get_send_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Triggered by /info command, send information on the video or playlist to user."""
    context.user_data.clear()
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

    # Validate url, if there is an error, send error message and return
    if error_message_text := await validate_youtube_url(url, context):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{error_message_text}. Please send a valid video or playlist URL.",
        )
        return

    processing_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"🔍 Fetching {context.user_data['url_type']} informations... Please wait.",
    )

    if cancel_event.is_set():
        return

    if context.user_data["url_type"] == "video":
        infos = await get_video_infos(context.user_data["videos_urls"][0])
        info_options = VIDEO_INFO_OPTIONS
    else:
        infos = await get_playlist_infos(context.user_data["url_id"])
        info_options = PLAYLIST_INFO_OPTIONS
        if hidden_videos_urls := await get_hidden_playlist_videos(
            context.user_data["videos_urls"], cancel_event
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


async def get_send_thumbnail(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Triggered by /thumbnail command, send video thumbnail to the user."""
    context.user_data.clear()
    context.user_data["conversation"] = False

    if not context.args:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Please provide a YouTube video URL." "\nExample: /thumbnail <URL>",
        )
        return

    url = context.args[0]

    # Validate url, if there is an error, send error message and return
    if error_message_text := await validate_youtube_url(url, context):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{error_message_text}. Please send a valid video URL.",
        )
        return

    if not context.user_data["url_type"] == "video":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ This is a playlist URL. Please send a video URL.",
        )
        return

    infos = await get_video_infos(context.user_data["videos_urls"][0])

    if not infos.get("thumbnail"):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Thumbnail not found for this video. Please try another one.",
        )
        return

    thumbnail_message = format_infos(infos, ["thumbnail"])

    if await send_thumbnail_photo(
        update, context, infos["thumbnail"], thumbnail_message
    ):
        return

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=thumbnail_message,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
        disable_notification=True,
    )

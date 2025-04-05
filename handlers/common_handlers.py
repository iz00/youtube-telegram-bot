"""
Telegram common handlers and helper functions used across multiple Telegram bot commands.

Includes:
- /cancel command handler.
- General error handler.
- Shared helper functions:
    - URL validation steps.
    - Thumbnail sending logic.
    - Cancellation checks during long operations.
"""

import asyncio

from telegram import Update
from telegram.error import BadRequest, TimedOut
from telegram.ext import ContextTypes, ConversationHandler

from utils.image_helpers import convert_image_to_jpeg, fetch_video_thumbnail
from utils.yt_helpers import (
    get_videos_urls,
    get_youtube_url_id,
    get_youtube_url_type,
    is_valid_youtube_url_format,
)


async def validate_youtube_url(
    url: str, context: ContextTypes.DEFAULT_TYPE
) -> str | None:
    """Validates the provided URL by performing a series of checks. 
    Returns an appropriate error message if any validation fails, or None if all checks pass. 
    Stores relevant data (url_type, url_id, videos_urls) in user data via context."""
    if not is_valid_youtube_url_format(url):
        return "❌ Invalid YouTube URL format"

    if not (
        (url_type := get_youtube_url_type(url))
        and (url_id := get_youtube_url_id(url, url_type))
    ):
        return "❌ Invalid YouTube URL"

    context.user_data["url_type"] = url_type
    context.user_data["url_id"] = url_id

    if not (videos_urls := await get_videos_urls(url_type, url_id)):
        return "❌ Unavailable YouTube URL"

    context.user_data["videos_urls"] = videos_urls

    return None


async def send_thumbnail_photo(update, context, thumbnail_url, caption) -> bool:
    """Download the thumbnail and try to send it as a photo with caption.
    Return True if thumbnail was succesfully sent with caption.
    Else, return False, and, if possible, send only the thumbnail in a message."""
    if not (original_image_data := await fetch_video_thumbnail(thumbnail_url)):
        return False

    if not (processed_image := convert_image_to_jpeg(original_image_data)):
        return False

    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=processed_image,
            caption=caption,
            parse_mode="MarkdownV2",
            disable_notification=True,
        )
        return True

    # Limit for Telegram caption length is 1024 characters
    # Some videos have long captions, so send only the thumbnail
    except BadRequest as e:
        print(f"Error sending photo with caption: {e}")

        if not (processed_image := convert_image_to_jpeg(original_image_data)):
            return False

        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=processed_image,
            disable_notification=True,
        )
        return False


async def check_for_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE, stop_event: asyncio.Event
):
    """Continuously check for /cancel while processing messages."""
    user_id = update.effective_user.id

    while not stop_event.is_set():
        try:
            new_update = await context.application.update_queue.get()
            if not new_update.message:
                continue

            # Only process "/cancel" from the same user
            if (
                new_update.message.text == "/cancel"
                and new_update.message.from_user.id == user_id
            ):
                # Stop processing messages
                stop_event.set()

                # Wait for any currently sending messages to finish
                await asyncio.sleep(0.5)

                # Clear any remaining messages in the queue
                while not context.application.update_queue.empty():
                    context.application.update_queue.get_nowait()

                await cancel(update, context)
                return

        except asyncio.CancelledError:
            return
        except Exception as e:
            print(f"Error checking for cancel: {e}")

        await asyncio.sleep(0.1)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finishes ongoing user process and/or ends conversation."""
    if context.user_data["conversation"]:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Process finished. Send /start to begin again.",
        )
        return ConversationHandler.END
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Process finished.",
        )
        return


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handles all errors and sends a friendly message to the user."""
    error = context.error

    print(f"An error occurred: {error}")

    if isinstance(error, TimedOut):
        error_message = "⏳ The request took too long and timed out. Please try again."
    else:
        error_message = "⚠️ An unexpected error occurred. Please try again."

    if update and isinstance(update, Update) and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=error_message,
            disable_notification=True,
        )

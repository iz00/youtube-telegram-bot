import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from config import BOT_TOKEN
from helpers import (
    is_valid_youtube_url_format,
    get_type_id_url,
    get_videos_urls,
    get_hidden_playlist_videos,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ConversationHandler states
URL = range(1)


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered by /help command, send instructions about the bot to user."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Send a YouTube video or playlist URL, and I'll fetch details like title, duration, views, likes, comments, and more!\nUse /start to begin.",
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered by /start command, start conversation with user (get URL and fetch details)."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Send a YouTube video or playlist URL.\n",
    )

    return URL


async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives a YouTube URL, validates it, and routes accordingly."""
    url = update.message.text.replace(" ", "")

    if not is_valid_youtube_url_format(url):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Invalid YouTube URL format. Please send a valid video or playlist URL.",
        )
        return URL

    url_info = get_type_id_url(url)

    if "error" in url_info:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Invalid YouTube URL. Please send a valid video or playlist URL.",
        )
        return URL

    videos_urls = get_videos_urls(url_info["type"], url_info["id"])

    if not videos_urls:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Unavailable YouTube URL. Please send a valid video or playlist URL.",
        )
        return URL

    context.user_data["url_info"] = url_info
    context.user_data["videos_urls"] = videos_urls

    if url_info["type"] == "playlist":
        return await handle_playlist(update, context)

    return ConversationHandler.END


async def handle_playlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles playlist processing by fetching videos and asking user to select."""

    hidden_videos = get_hidden_playlist_videos(context.user_data["videos_urls"])

    if hidden_videos:
        context.user_data["playlist_hidden_videos"] = hidden_videos

        # Keep only avaliable videos in videos_urls
        context.user_data["videos_urls"] = [
            url for url in context.user_data["videos_urls"] if url not in hidden_videos
        ]

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"This playlist has {len(context.user_data['videos_urls'])} available videos.\n"
        "Choose which videos you want (e.g., 2, 4-7, 9). Or click 'All' to get all videos.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="All", callback_data="all")]]
        ),
    )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finishes the conversation."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Process finished. Send /start to begin again.",
    )

    return ConversationHandler.END


if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    help_handler = CommandHandler("help", help)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_url)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    application.add_handler(help_handler)
    application.add_handler(conv_handler)

    application.run_polling()

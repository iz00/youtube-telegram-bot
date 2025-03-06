import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
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
    parse_video_selection,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ConversationHandler states
URL, SELECT_VIDEOS = range(2)

# Options available to users
VIDEO_OPTIONS = [
    "title",
    "duration",
    "views count",
    "likes count",
    "comments count",
    "upload date",
    "description",
    "uploader",
    "thumbnail",
]
PLAYLIST_OPTIONS = [
    "playlist title",
    "playlist description",
    "playlist thumbnail",
    "playlist uploader",
    "playlist hidden videos",
]


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

    return SELECT_VIDEOS


async def receive_video_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes user's selection of videos from the playlist."""
    query = update.callback_query

    # If user didn't click 'All' button
    if not query:
        user_input = update.message.text.replace(" ", "")
        selected_indices = parse_video_selection(
            user_input, len(context.user_data["videos_urls"])
        )

        if not selected_indices:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Invalid selection. Please try again.\n"
                "Choose which videos you want (e.g., 2, 4-7, 9). Or click 'All' to get all videos.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="All", callback_data="all")]]
                ),
            )
            return SELECT_VIDEOS

        context.user_data["playlist_available_videos"] = context.user_data[
            "videos_urls"
        ]

        context.user_data["videos_urls"] = [
            context.user_data["videos_urls"][i - 1] for i in selected_indices
        ]

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"You selected the videos: {context.user_data['videos_urls']}.",
    )

    return ConversationHandler.END


def build_options_keyboard(selected_options, is_playlist):
    """Build inline keyboard with options.
    Add an indication on already selected options."""
    options = VIDEO_OPTIONS + PLAYLIST_OPTIONS if is_playlist else VIDEO_OPTIONS
    keyboard = []

    # Add option buttons in two columns
    buttons_row = []
    for option in options:
        selected_indication = "✔️ " if option in selected_options else ""
        buttons_row.append(
            InlineKeyboardButton(
                f"{selected_indication}{option.title()}", callback_data=option
            )
        )

        if len(buttons_row) == 2:
            keyboard.append(buttons_row)
            buttons_row = []

    # If there's an odd number of options, append the last row
    if buttons_row:
        keyboard.append(buttons_row)

    # Add a "Select All"/"Deselect All" button
    all_selected = set(options).issubset(selected_options)
    select_all_label = "Select All" if not all_selected else "Deselect All"
    keyboard.append(
        [InlineKeyboardButton(select_all_label, callback_data="select_all")]
    )

    keyboard.append([InlineKeyboardButton("✅ Done", callback_data="done")])

    return InlineKeyboardMarkup(keyboard)


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
            SELECT_VIDEOS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, receive_video_selection
                ),
                CallbackQueryHandler(receive_video_selection, pattern="^all$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    application.add_handler(help_handler)
    application.add_handler(conv_handler)

    application.run_polling()

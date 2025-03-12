import logging, requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
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
    get_video_infos,
    get_playlist_infos,
    format_videos_urls,
    format_infos,
    split_message,
    process_image,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ConversationHandler states
URL, SELECT_VIDEOS, SELECT_OPTIONS = range(3)

# Options available to users
VIDEO_OPTIONS = [
    "title",
    "duration",
    "views count",
    "likes count",
    "comments count",
    "upload date",
    "uploader",
    "description",
    "chapters",
    "thumbnail",
]
PLAYLIST_OPTIONS = [
    "playlist title",
    "playlist description",
    "playlist uploader",
]

# Options that have statistics
OPTIONS_WITH_STATS = [
    "duration",
    "views count",
    "likes count",
    "comments count",
]


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered by /help command, send instructions about the bot to user."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Send a YouTube video or playlist URL, and I'll fetch details like title, duration, views, likes, comments, and more!\nUse /start to begin.",
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered by /start command, start conversation with user (get URL and fetch details)."""
    context.user_data.clear()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Send a YouTube video or playlist URL.\n",
    )

    return URL


async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives a YouTube URL, validates it, and routes accordingly."""
    url = update.message.text.replace(" ", "")

    # Delete previous wrong and error messages (if exists)
    for message in ["last_error_message_id", "last_invalid_user_message_id"]:
        if message in context.user_data:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=context.user_data[message],
                )
            # Message might have already been deleted
            except BadRequest:
                pass

    error_message = None

    if not is_valid_youtube_url_format(url):
        error_message = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Invalid YouTube URL format. Please send a valid video or playlist URL.",
        )

    elif "error" in (url_info := get_type_id_url(url)):
        error_message = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Invalid YouTube URL. Please send a valid video or playlist URL.",
        )

    elif not (videos_urls := get_videos_urls(url_info["type"], url_info["id"])):
        error_message = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Unavailable YouTube URL. Please send a valid video or playlist URL.",
        )

    # If there was an error, store message IDs and return
    if error_message:
        context.user_data["last_error_message_id"] = error_message.message_id
        context.user_data["last_invalid_user_message_id"] = update.message.message_id
        return URL

    # Delete previous wrong and error messages (if exists) from user_data
    context.user_data.pop("last_error_message_id", None)
    context.user_data.pop("last_invalid_user_message_id", None)

    context.user_data["url_info"] = url_info
    context.user_data["videos_urls"] = videos_urls

    if url_info["type"] == "playlist":
        return await handle_playlist(update, context)

    context.user_data["selected_options"] = set()
    return await show_options_menu(update, context)


async def handle_playlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles playlist processing by fetching videos and asking user to select."""

    hidden_videos = get_hidden_playlist_videos(context.user_data["videos_urls"])

    if hidden_videos:
        context.user_data["playlist_hidden_videos"] = hidden_videos

        # Keep only avaliable videos in videos_urls
        context.user_data["videos_urls"] = [
            url for url in context.user_data["videos_urls"] if url not in hidden_videos
        ]

    video_selection_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"This playlist has {len(context.user_data['videos_urls'])} available videos.\n"
        "Choose which videos you want (e.g., 2, 4-7, 9).\n"
        "Or click 'All' to get all videos.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="All", callback_data="all")]]
        ),
    )

    context.user_data["video_selection_message"] = video_selection_message.message_id

    return SELECT_VIDEOS


async def receive_video_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes user's selection of videos from the playlist."""
    query = update.callback_query

    # Delete previous wrong and error messages (if exists)
    for message in ["last_error_message_id", "last_invalid_user_message_id"]:
        if message in context.user_data:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=context.user_data[message],
                )
            # Message might have already been deleted
            except BadRequest:
                pass

    # If user didn't click 'All' button
    if not query:
        user_input = update.message.text.replace(" ", "")
        selected_indices = parse_video_selection(
            user_input, len(context.user_data["videos_urls"])
        )

        if not selected_indices:
            error_message = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Invalid selection. Please try again.",
            )
            context.user_data["last_error_message_id"] = error_message.message_id
            context.user_data["last_invalid_user_message_id"] = (
                update.message.message_id
            )
            return SELECT_VIDEOS

        context.user_data["playlist_available_videos"] = context.user_data[
            "videos_urls"
        ]

        context.user_data["videos_urls"] = [
            context.user_data["videos_urls"][i - 1] for i in selected_indices
        ]

    # Delete previous wrong and error messages (if exists) from user_data
    context.user_data.pop("last_error_message_id", None)
    context.user_data.pop("last_invalid_user_message_id", None)

    # Edit message with "All" button so it can't be used anymore
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=context.user_data["video_selection_message"],
        text=f"This playlist has {len(context.user_data['videos_urls'])} available videos.\n",
    )
    context.user_data.pop("video_selection_message", None)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"You selected the videos:\n{format_videos_urls(context.user_data['videos_urls'])}",
        disable_web_page_preview=True,
    )

    context.user_data["selected_options"] = set()
    return await show_options_menu(update, context)


def build_options_keyboard(selected_options, is_playlist, has_hidden_videos):
    """Build inline keyboard with options.
    Add an indication on already selected options."""
    options = VIDEO_OPTIONS[:]

    if is_playlist:
        options += PLAYLIST_OPTIONS
        if has_hidden_videos:
            options.append("playlist hidden videos")

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

    if selected_options:
        keyboard.append([InlineKeyboardButton("✅ Done", callback_data="done")])

    return InlineKeyboardMarkup(keyboard)


async def show_options_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show options selection menu."""
    is_playlist = context.user_data["url_info"]["type"] == "playlist"
    has_hidden_videos = len(context.user_data.get("playlist_hidden_videos", {})) > 0

    keyboard = build_options_keyboard(
        context.user_data["selected_options"], is_playlist, has_hidden_videos
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Select the options you want:",
        reply_markup=keyboard,
    )

    return SELECT_OPTIONS


async def receive_option_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user selection/unselection of options."""
    query = update.callback_query
    option = query.data

    if option == "done":
        # Sort user's selected options in the correct order
        correct_order = VIDEO_OPTIONS + PLAYLIST_OPTIONS
        context.user_data["selected_options"] = sorted(
            context.user_data["selected_options"],
            key=lambda option: (
                correct_order.index(option) if option in correct_order else float("inf")
            ),
        )

        await query.message.edit_text(
            "You selected:\n"
            + "\n".join(
                option.title() for option in context.user_data["selected_options"]
            )
        )

        return await send_user_info(update, context)

    is_playlist = context.user_data["url_info"]["type"] == "playlist"
    options = VIDEO_OPTIONS + PLAYLIST_OPTIONS if is_playlist else VIDEO_OPTIONS

    has_hidden_videos = len(context.user_data.get("playlist_hidden_videos", {})) > 0
    if has_hidden_videos:
        options.append("playlist hidden videos")

    if option == "select_all":
        if set(options).issubset(context.user_data["selected_options"]):
            context.user_data["selected_options"].clear()
        else:
            context.user_data["selected_options"] = set(options)
    else:
        if option in context.user_data["selected_options"]:
            context.user_data["selected_options"].remove(option)
        else:
            context.user_data["selected_options"].add(option)

    keyboard = build_options_keyboard(
        context.user_data["selected_options"], is_playlist, has_hidden_videos
    )
    await query.message.edit_reply_markup(reply_markup=keyboard)

    return SELECT_OPTIONS


async def send_thumbnail_photo(update, context, thumbnail_url, caption):
    """Download the thumbnail and try to send it as a photo with caption.
    Return True if thumbnail was succesfully sent with caption.
    Else, return False, and, if possible, send only the thumbnail in a message."""
    try:
        response = requests.get(thumbnail_url, stream=True)
        response.raise_for_status()
        original_image_data = response.content
    except requests.exceptions.RequestException as e:
        print(f"Error downloading thumbnail: {e}")
        return False

    processed_image = process_image(original_image_data)
    if not processed_image:
        return False

    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=processed_image,
            caption=caption,
            parse_mode="MarkdownV2",
        )
        return True

    # Limit for Telegram caption length is 1024 characters
    # Some videos have long captions, so send only the thumbnail
    except BadRequest as e:
        print(f"Error sending photo with caption: {e}")

        processed_image = process_image(original_image_data)
        if not processed_image:
            return False

        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=processed_image,
        )
        return False


async def send_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the user the requested information."""
    has_playlist_info = any(
        "playlist" in option for option in context.user_data["selected_options"]
    )

    if has_playlist_info:
        playlist_info = get_playlist_infos(context.user_data["url_info"]["id"])
        if len(context.user_data.get("playlist_hidden_videos", {})) > 0:
            playlist_info["playlist hidden videos"] = context.user_data[
                "playlist_hidden_videos"
            ]

        message = format_infos(playlist_info, context.user_data["selected_options"])
        for chunk in split_message(message):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=chunk,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True,
            )

    total_stats = None

    if (video_count := len(context.user_data["videos_urls"])) > 1:
        selected_stats = [
            stat
            for stat in OPTIONS_WITH_STATS
            if stat in context.user_data["selected_options"]
        ]
        if selected_stats:
            total_stats = {option: 0 for option in selected_stats}

    for video_url in context.user_data["videos_urls"]:
        video_info = get_video_infos(video_url)
        send_thumbnail = "thumbnail" in context.user_data[
            "selected_options"
        ] and video_info.get("thumbnail")

        message = format_infos(video_info, context.user_data["selected_options"])

        if send_thumbnail:
            sent_thumbnail_with_caption = await send_thumbnail_photo(
                update, context, video_info["thumbnail"], message
            )
            if sent_thumbnail_with_caption:
                continue

        # If thumbnail wasn't sent with caption, or if send_thumbnail was False, send the text message
        for chunk in split_message(message):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=chunk,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True,
            )

        if video_count > 1 and selected_stats:
            for stat in selected_stats:
                if isinstance(video_info.get(stat), (int, float)):
                    total_stats[stat] += video_info[stat]

    if total_stats and any(value > 0 for value in total_stats.values()):
        formatted_total_message = format_infos(total_stats, selected_stats)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="*Total Statistics:*\n\n" + formatted_total_message,
            parse_mode="MarkdownV2",
        )

        average_stats = {
            stat: int(value) if value.is_integer() else round(value, 2)
            for stat, value in ((s, total_stats[s] / video_count) for s in total_stats)
        }
        formatted_average_message = format_infos(average_stats, selected_stats)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="*Average Statistics per Video:*\n\n" + formatted_average_message,
            parse_mode="MarkdownV2",
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
            SELECT_VIDEOS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, receive_video_selection
                ),
                CallbackQueryHandler(receive_video_selection, pattern="^all$"),
            ],
            SELECT_OPTIONS: [CallbackQueryHandler(receive_option_selection)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    application.add_handler(help_handler)
    application.add_handler(conv_handler)

    application.run_polling()

import asyncio, logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TimedOut
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
    escape_markdown_v2,
    format_infos,
    split_message,
    fetch_thumbnail,
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
    text = (
        f"🤖 *{escape_markdown_v2('Welcome to the YouTube Info Bot!')}* 🎬\n\n"
        "Send a **YouTube video** or **playlist URL**, and I'll fetch details like:\n"
        f"📌 *Title*, ⏳ *Duration*, 👀 *Views*, 👍 *Likes*, 💬 *Comments*, {escape_markdown_v2('and more!')}\n\n"
        "✅ *Commands:*\n"
        f"• /start – {escape_markdown_v2('Begin interaction.')}\n"
        f"• /cancel – {escape_markdown_v2('Stop any ongoing process.')}\n\n"
        "ℹ️ *More Help:*\n"
        f"• {escape_markdown_v2('/help_url – Details on valid YouTube URLs.')}\n"
        f"• {escape_markdown_v2('/help_infos – Information that can be fetched.')}\n"
        f"• {escape_markdown_v2('/help_commands – Other available commands.')}"
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=text, parse_mode="MarkdownV2"
    )


async def help_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered by /help_url command, send information on valid URLs to user."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "🔗 *Supported URL formats:*\n\n"
            f"🎥 *Videos:* Any valid YouTube video URL _{escape_markdown_v2('(including shorts & youtu.​be links)')}_{escape_markdown_v2('.')}\n"
            f"📜 *Playlists:* Only URLs like `{escape_markdown_v2('youtube.​com/playlist?list=<playlist_ID>')}`{escape_markdown_v2('.')}\n\n"
            "⚠️ *Note:* Videos that are part of playlists \n"
            f"_{escape_markdown_v2('(e.g.')} `{escape_markdown_v2('youtube.​com/watch?v=<video_ID>&list=<playlist_ID>')}`{escape_markdown_v2(')')}_ {escape_markdown_v2('are treated as single videos.')}\n"
            f"🎯 {escape_markdown_v2('You can select specific videos from a playlist!')}"
        ),
        parse_mode="MarkdownV2",
    )


async def help_infos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered by /help_infos command, send information on available infos to user."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "ℹ️ *Available Information:*\n\n"
            "🎥 *For videos:*\n"
            "• *Title*\n"
            "• *Duration*\n"
            "• *Views Count*\n"
            "• *Likes Count*\n"
            "• *Comments Count*\n"
            "• *Upload Date*\n"
            "• *Uploader*\n"
            "• *Description*\n"
            "• *Chapters*\n"
            "• *Thumbnail*\n\n"
            "📜 *For playlists:*\n"
            "• *Title*\n"
            "• *Description*\n"
            "• *Uploader*\n\n"
            "📊 *For playlist videos:*\n"
            "• *Total & Average:* _Duration, Views, Likes, Comments_\n\n"
            f"🎯 {escape_markdown_v2('You can select which details to fetch!')}"
        ),
        parse_mode="MarkdownV2",
    )


async def help_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered by /help_commands command, send information on other commands to user."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "⚙️ *Available Commands:*\n\n"
            f"🔍 `/info <URL>` – Get all details about a YouTube *video* or *playlist*{escape_markdown_v2('.')}\n"
            f"📸 `/thumbnail <URL>` – Get the *thumbnail* of a YouTube video{escape_markdown_v2('.')}\n\n"
            f"⚠️ *Note:* For playlists, `/info` does *not* fetch details for each video{escape_markdown_v2('.')}\n"
        ),
        parse_mode="MarkdownV2",
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered by /start command, start conversation with user (get URL and fetch details)."""
    context.user_data.clear()
    context.user_data["conversation"] = True
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

    elif not (videos_urls := await get_videos_urls(url_info["type"], url_info["id"])):
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
                return "CANCELED"

        except asyncio.CancelledError:
            return
        except Exception as e:
            print(f"Error checking for cancel: {e}")

        await asyncio.sleep(0.1)


async def handle_playlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles playlist processing by fetching videos and asking user to select."""
    stop_event = asyncio.Event()
    check_task = asyncio.create_task(check_for_cancel(update, context, stop_event))

    video_processing_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔍 Checking the playlist videos... Please wait.",
    )

    hidden_videos = await get_hidden_playlist_videos(
        context.user_data["videos_urls"], stop_event
    )

    if stop_event.is_set():
        return

    if hidden_videos:
        context.user_data["playlist_hidden_videos"] = hidden_videos

        # Keep only avaliable videos in videos_urls
        context.user_data["videos_urls"] = [
            url for url in context.user_data["videos_urls"] if url not in hidden_videos
        ]

    context.user_data["playlist_available_videos"] = context.user_data["videos_urls"]

    if stop_event.is_set():
        return

    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=video_processing_message.message_id,
        text=f"This playlist has {len(context.user_data['playlist_available_videos'])} available videos.\n"
        "Choose which videos you want (e.g., 2, 4-7, 9).\n"
        "Or click 'None' or 'All'.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text="None", callback_data="none"),
                    InlineKeyboardButton(text="All", callback_data="all"),
                ]
            ]
        ),
    )

    check_task.cancel()

    context.user_data["video_selection_message"] = video_processing_message.message_id

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

    # If user clicked one of the buttons
    if query:
        await query.answer()
        if query.data == "none":
            context.user_data["videos_urls"] = []
        elif query.data == "all":
            context.user_data["videos_urls"] = context.user_data[
                "playlist_available_videos"
            ]
    else:
        user_input = update.message.text.replace(" ", "")
        selected_indices = parse_video_selection(
            user_input, len(context.user_data["playlist_available_videos"])
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

        context.user_data["videos_urls"] = [
            context.user_data["playlist_available_videos"][i - 1]
            for i in selected_indices
        ]

    # Delete previous wrong and error messages (if exists) from user_data
    context.user_data.pop("last_error_message_id", None)
    context.user_data.pop("last_invalid_user_message_id", None)

    # Edit message with "None" and "All" buttons so they can't be used anymore
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=context.user_data["video_selection_message"],
        text=f"This playlist has {len(context.user_data['playlist_available_videos'])} available videos.\n",
    )
    context.user_data.pop("video_selection_message", None)

    if context.user_data["videos_urls"]:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"You selected the videos:\n{format_videos_urls(context.user_data['videos_urls'])}",
            disable_web_page_preview=True,
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="You selected no videos.",
        )

    context.user_data["selected_options"] = set()
    return await show_options_menu(update, context)


def build_options_keyboard(
    selected_options, has_videos, is_playlist, has_hidden_videos
):
    """Build inline keyboard with options.
    Add an indication on already selected options."""
    options = VIDEO_OPTIONS[:] if has_videos else []

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

    if is_playlist:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "Select Different Playlist Videos", callback_data="select_videos"
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])

    if selected_options:
        keyboard.append([InlineKeyboardButton("✅ Done", callback_data="done")])

    return InlineKeyboardMarkup(keyboard)


async def show_options_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show options selection menu."""
    is_playlist = context.user_data["url_info"]["type"] == "playlist"
    has_hidden_videos = len(context.user_data.get("playlist_hidden_videos", {})) > 0

    keyboard = build_options_keyboard(
        context.user_data["selected_options"],
        bool(context.user_data["videos_urls"]),
        is_playlist,
        has_hidden_videos,
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

    elif option == "select_videos":
        await query.message.edit_text(
            text=f"This playlist has {len(context.user_data['playlist_available_videos'])} available videos.\n"
            "Choose which videos you want (e.g., 2, 4-7, 9).\n"
            "Or click 'None' or 'All'.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(text="None", callback_data="none"),
                        InlineKeyboardButton(text="All", callback_data="all"),
                    ]
                ]
            ),
        )

        context.user_data["video_selection_message"] = query.message.message_id

        return SELECT_VIDEOS

    elif option == "cancel":
        await query.message.edit_text("Process finished. Send /start to begin again.")
        return ConversationHandler.END

    has_videos = bool(context.user_data["videos_urls"])
    is_playlist = context.user_data["url_info"]["type"] == "playlist"
    has_hidden_videos = bool(context.user_data.get("playlist_hidden_videos"))

    options = VIDEO_OPTIONS[:] if has_videos else []
    if is_playlist:
        options += PLAYLIST_OPTIONS
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
        context.user_data["selected_options"],
        has_videos,
        is_playlist,
        has_hidden_videos,
    )
    await query.message.edit_reply_markup(reply_markup=keyboard)

    return SELECT_OPTIONS


async def send_thumbnail_photo(update, context, thumbnail_url, caption):
    """Download the thumbnail and try to send it as a photo with caption.
    Return True if thumbnail was succesfully sent with caption.
    Else, return False, and, if possible, send only the thumbnail in a message."""
    if not (original_image_data := await fetch_thumbnail(thumbnail_url)):
        return False

    if not (processed_image := process_image(original_image_data)):
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

        if not (processed_image := process_image(original_image_data)):
            return False

        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=processed_image,
            disable_notification=True,
        )
        return False


async def send_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the user the requested information."""
    stop_event = asyncio.Event()
    check_task = asyncio.create_task(check_for_cancel(update, context, stop_event))

    async def send_text(text):
        """Send text message while checking for stop signal."""
        if stop_event.is_set():
            return False
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
            disable_notification=True,
        )
        return True

    async def send_thumbnail(thumbnail_url, caption):
        """Send thumbnail while checking for stop signal."""
        if stop_event.is_set():
            return False
        return await send_thumbnail_photo(update, context, thumbnail_url, caption)

    has_playlist_info = any(
        "playlist" in option for option in context.user_data["selected_options"]
    )

    if has_playlist_info:
        playlist_info = await get_playlist_infos(context.user_data["url_info"]["id"])
        if len(context.user_data.get("playlist_hidden_videos", {})) > 0:
            playlist_info["playlist hidden videos"] = context.user_data[
                "playlist_hidden_videos"
            ]

        message = format_infos(playlist_info, context.user_data["selected_options"])
        for chunk in split_message(message):
            if not await send_text(chunk):
                return

    total_stats = None

    if (video_count := len(context.user_data["videos_urls"])) > 1:
        selected_stats = [
            stat
            for stat in OPTIONS_WITH_STATS
            if stat in context.user_data["selected_options"]
        ]
        if selected_stats:
            total_stats = {option: 0 for option in selected_stats}

    if any(option in VIDEO_OPTIONS for option in context.user_data["selected_options"]):
        for video_url in context.user_data["videos_urls"]:
            if stop_event.is_set():
                return

            video_info = await get_video_infos(video_url)
            has_send_thumbnail = "thumbnail" in context.user_data[
                "selected_options"
            ] and video_info.get("thumbnail")

            message = format_infos(video_info, context.user_data["selected_options"])

            if has_send_thumbnail:
                if await send_thumbnail(video_info["thumbnail"], message):
                    continue

            # If thumbnail wasn't sent with caption, or if has_send_thumbnail was False, send the text message
            for chunk in split_message(message):
                if not await send_text(chunk):
                    return

            if video_count > 1 and selected_stats:
                for stat in selected_stats:
                    if isinstance(video_info.get(stat), (int, float)):
                        total_stats[stat] += video_info[stat]

    if total_stats and any(value > 0 for value in total_stats.values()):
        await send_text(
            "*Total Statistics:*\n\n" + format_infos(total_stats, selected_stats)
        )

        average_stats = {
            stat: int(value) if value.is_integer() else round(value, 2)
            for stat, value in ((s, total_stats[s] / video_count) for s in total_stats)
        }
        await send_text(
            "*Average Statistics per Video:*\n\n"
            + format_infos(average_stats, selected_stats)
        )

    check_task.cancel()

    context.user_data["selected_options"] = set()
    return await show_options_menu(update, context)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handles all errors and sends a friendly message to the user."""
    error = context.error

    print(f"An error occurred: {error}")

    if isinstance(error, TimedOut):
        error_message = "⏳ The request took too long and timed out. Please try again."
    else:
        error_message = "⚠ An unexpected error occurred. Please try again."

    if update and isinstance(update, Update) and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=error_message,
            disable_notification=True,
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finishes the conversation."""
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

    if "error" in (url_info := get_type_id_url(url)):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Invalid YouTube URL. Please send a valid video or playlist URL.",
        )
        return

    if stop_event.is_set():
        return

    if not (videos_urls := await get_videos_urls(url_info["type"], url_info["id"])):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Unavailable YouTube URL. Please send a valid video or playlist URL.",
        )
        return

    processing_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"🔍 Fetching {url_info['type']} informations... Please wait.",
    )

    if stop_event.is_set():
        return

    if url_info["type"] == "video":
        infos = await get_video_infos(videos_urls[0])
        options = VIDEO_OPTIONS
    else:
        infos = await get_playlist_infos(url_info["id"])
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

    if "error" in (url_info := get_type_id_url(url)):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: Invalid YouTube URL. Please send a valid video URL.",
        )
        return

    if not url_info["type"] == "video":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error: This is a playlist URL. Please send a video URL.",
        )
        return

    if not (videos_urls := await get_videos_urls(url_info["type"], url_info["id"])):
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


if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_error_handler(error_handler)

    help_handler = CommandHandler("help", help)
    help_url_handler = CommandHandler("help_url", help_url)
    help_infos_handler = CommandHandler("help_infos", help_infos)
    help_commands_handler = CommandHandler("help_commands", help_commands)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_url)],
            SELECT_VIDEOS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, receive_video_selection
                ),
                CallbackQueryHandler(receive_video_selection, pattern="^(all|none)$"),
            ],
            SELECT_OPTIONS: [CallbackQueryHandler(receive_option_selection)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    info_handler = CommandHandler("info", get_send_info, block=False)
    thumbnail_handler = CommandHandler("thumbnail", get_send_thumbnail, block=False)

    application.add_handler(help_handler)
    application.add_handler(help_url_handler)
    application.add_handler(help_infos_handler)
    application.add_handler(help_commands_handler)
    application.add_handler(conv_handler)
    application.add_handler(info_handler)
    application.add_handler(thumbnail_handler)

    application.run_polling()

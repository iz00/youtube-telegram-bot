import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from handlers.common_handlers import (
    cancel,
    check_for_cancel,
    send_thumbnail_photo,
    validate_youtube_url,
)

from utils.bot_data import (
    PLAYLIST_INFO_OPTIONS,
    PROVIDE_URL,
    SELECT_INFO_OPTIONS,
    SELECT_VIDEOS,
    STATISTICAL_INFO_OPTIONS,
    VIDEO_INFO_OPTIONS,
)
from utils.format_helpers import (
    format_infos,
    format_video_urls,
    parse_videos_selection,
    split_message,
)
from utils.yt_helpers import (
    get_hidden_playlist_videos,
    get_playlist_infos,
    get_video_infos,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered by /start command, start conversation with user (get URL and fetch details)."""
    context.user_data.clear()
    context.user_data["conversation"] = True
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Send a YouTube video or playlist URL.",
    )

    return PROVIDE_URL


async def get_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives a YouTube URL, validates it, and routes accordingly."""
    url = update.message.text.replace(" ", "")

    # Delete previous not valid user message and error message (if exists)
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

    # Validate url, if there is an error, send error message, store message IDs and return
    if error_message_text := await validate_youtube_url(url, context):
        error_message = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{error_message_text}. Please send a valid video or playlist URL.",
        )

        context.user_data["last_error_message_id"] = error_message.message_id
        context.user_data["last_invalid_user_message_id"] = update.message.message_id
        return PROVIDE_URL

    # Delete previous wrong and error messages (if exists) from user_data
    context.user_data.pop("last_error_message_id", None)
    context.user_data.pop("last_invalid_user_message_id", None)

    if context.user_data["url_type"] == "playlist":
        return await handle_playlist(update, context)

    context.user_data["selected_info_options"] = set()
    return await send_info_options_menu(update, context)


async def handle_playlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles playlist processing by fetching videos and asking user to select."""
    cancel_event = asyncio.Event()
    check_cancel_task = asyncio.create_task(
        check_for_cancel(update, context, cancel_event)
    )

    videos_processing_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔍 Checking the playlist videos... Please wait.",
    )

    if cancel_event.is_set():
        return

    if hidden_videos_urls := await get_hidden_playlist_videos(
        context.user_data["videos_urls"], cancel_event
    ):
        context.user_data["playlist_hidden_videos"] = hidden_videos_urls

        # Keep only avaliable videos in videos_urls
        context.user_data["videos_urls"] = [
            url
            for url in context.user_data["videos_urls"]
            if url not in hidden_videos_urls
        ]

    context.user_data["playlist_available_videos"] = context.user_data["videos_urls"]

    if cancel_event.is_set():
        return

    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=videos_processing_message.message_id,
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

    check_cancel_task.cancel()

    context.user_data["video_selection_message"] = videos_processing_message.message_id

    return SELECT_VIDEOS


async def get_selected_playlist_videos(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Processes user's selection of videos from the playlist."""
    query = update.callback_query

    # Delete previous not valid user message and error message (if exists)
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

        if not (
            selected_indices := parse_videos_selection(
                user_input, len(context.user_data["playlist_available_videos"])
            )
        ):
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
        selected_videos_message = f"You selected the videos:\n{format_video_urls(context.user_data['videos_urls'])}"
    else:
        selected_videos_message = "You selected no videos."

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=selected_videos_message,
        disable_web_page_preview=True,
    )

    context.user_data["selected_info_options"] = set()
    return await send_info_options_menu(update, context)


def build_info_options_keyboard(
    available_info_options, selected_info_options, is_playlist
) -> InlineKeyboardMarkup:
    """Build inline keyboard with info options.
    Add an indication on already selected options."""
    keyboard = []

    # Add option buttons in two columns
    buttons_row = []
    for option in available_info_options:
        selected_indication = "✔️ " if option in selected_info_options else ""
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
    is_all_options_selected = set(available_info_options).issubset(
        selected_info_options
    )
    toggle_all_label = "Select All" if not is_all_options_selected else "Deselect All"
    keyboard.append(
        [InlineKeyboardButton(toggle_all_label, callback_data="toggle_all")]
    )

    if is_playlist:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "Select Different Playlist Videos",
                    callback_data="select_different_videos",
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])

    if selected_info_options:
        keyboard.append([InlineKeyboardButton("✅ Done", callback_data="done")])

    return InlineKeyboardMarkup(keyboard)


async def send_info_options_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show info options selection menu."""
    context.user_data["available_info_options"] = set()
    context.user_data["available_info_options"] = (
        VIDEO_INFO_OPTIONS[:] if bool(context.user_data.get("videos_urls")) else []
    )

    if is_playlist := context.user_data["url_type"] == "playlist":
        context.user_data["available_info_options"] += PLAYLIST_INFO_OPTIONS
        if bool(context.user_data.get("playlist_hidden_videos")):
            context.user_data["available_info_options"].append("playlist hidden videos")

    info_options_keyboard = build_info_options_keyboard(
        available_info_options=context.user_data["available_info_options"],
        selected_info_options=context.user_data["selected_info_options"],
        is_playlist=is_playlist,
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Select the options you want:",
        reply_markup=info_options_keyboard,
    )

    return SELECT_INFO_OPTIONS


async def get_selected_info_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user selection/unselection of options."""
    query = update.callback_query
    await query.answer()
    selected_info_option = query.data

    if selected_info_option == "done":
        # Sort user's selected options in the correct order
        info_options_correct_order = VIDEO_INFO_OPTIONS + PLAYLIST_INFO_OPTIONS

        context.user_data["selected_info_options"] = sorted(
            context.user_data["selected_info_options"],
            key=lambda option: (
                info_options_correct_order.index(option)
                if option in info_options_correct_order
                else float("inf")
            ),
        )

        await query.message.edit_text(
            "You selected:\n"
            + "\n".join(
                option.title() for option in context.user_data["selected_info_options"]
            )
        )

        return await send_infos(update, context)

    elif selected_info_option == "select_different_videos":
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

    elif selected_info_option == "cancel":
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=query.message.id,
        )
        return await cancel(update, context)

    if selected_info_option == "toggle_all":
        if set(context.user_data["available_info_options"]).issubset(
            context.user_data["selected_info_options"]
        ):
            context.user_data["selected_info_options"].clear()
        else:
            context.user_data["selected_info_options"] = set(
                context.user_data["available_info_options"]
            )

    else:
        if selected_info_option in context.user_data["selected_info_options"]:
            context.user_data["selected_info_options"].remove(selected_info_option)
        else:
            context.user_data["selected_info_options"].add(selected_info_option)

    info_options_keyboard = build_info_options_keyboard(
        available_info_options=context.user_data["available_info_options"],
        selected_info_options=context.user_data["selected_info_options"],
        is_playlist=context.user_data["url_type"] == "playlist",
    )
    await query.message.edit_reply_markup(reply_markup=info_options_keyboard)

    return SELECT_INFO_OPTIONS


async def send_infos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the user the requested information."""
    cancel_event = asyncio.Event()
    check_cancel_task = asyncio.create_task(
        check_for_cancel(update, context, cancel_event)
    )

    async def send_message_checking_cancel(message: str) -> bool:
        """Send text message while checking for cancel command."""
        if cancel_event.is_set():
            return False

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
            disable_notification=True,
        )

        return True

    async def send_thumbnail_checking_cancel(thumbnail_url: str, caption: str) -> bool:
        """Send thumbnail while checking for cancel command."""
        if cancel_event.is_set():
            return False

        return await send_thumbnail_photo(update, context, thumbnail_url, caption)

    if any(
        "playlist" in option for option in context.user_data["selected_info_options"]
    ):
        playlist_infos = await get_playlist_infos(context.user_data["url_id"])

        if bool(context.user_data.get("playlist_hidden_videos")):
            playlist_infos["playlist hidden videos"] = context.user_data[
                "playlist_hidden_videos"
            ]

        message = format_infos(
            playlist_infos, context.user_data["selected_info_options"]
        )

        for chunk in split_message(message):
            if not await send_message_checking_cancel(chunk):
                return

    total_statistics_infos = None

    if (video_count := len(context.user_data["videos_urls"])) > 1:
        selected_statistical_info_options = [
            option
            for option in STATISTICAL_INFO_OPTIONS
            if option in context.user_data["selected_info_options"]
        ]
        if selected_statistical_info_options:
            total_statistics_infos = {
                option: 0 for option in selected_statistical_info_options
            }

    if any(
        option in VIDEO_INFO_OPTIONS
        for option in context.user_data["selected_info_options"]
    ):
        for video_url in context.user_data["videos_urls"]:
            if cancel_event.is_set():
                return

            video_infos = await get_video_infos(video_url)

            if selected_statistical_info_options:
                for option in selected_statistical_info_options:
                    if isinstance(video_infos.get(option), (int, float)):
                        total_statistics_infos[option] += video_infos[option]

            message = format_infos(
                video_infos, context.user_data["selected_info_options"]
            )

            if "thumbnail" in context.user_data[
                "selected_info_options"
            ] and video_infos.get("thumbnail"):
                if await send_thumbnail_checking_cancel(
                    video_infos["thumbnail"], message
                ):
                    continue

            # If thumbnail wasn't sent with caption, or if it won't be sent, send the text message
            for chunk in split_message(message):
                if not await send_message_checking_cancel(chunk):
                    return

    if total_statistics_infos and any(
        info_value > 0 for info_value in total_statistics_infos.values()
    ):
        await send_message_checking_cancel(
            "*Total Statistics:*\n\n"
            + format_infos(total_statistics_infos, selected_statistical_info_options)
        )

        average_statistics_infos = {
            info: int(info_value) if info_value.is_integer() else round(info_value, 2)
            for info, info_value in (
                (total_info, total_statistics_infos[total_info] / video_count)
                for total_info in total_statistics_infos
            )
        }

        await send_message_checking_cancel(
            "*Average Statistics:*\n\n"
            + format_infos(average_statistics_infos, selected_statistical_info_options)
        )

    check_cancel_task.cancel()

    context.user_data["selected_info_options"].clear()
    return await send_info_options_menu(update, context)

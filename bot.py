import logging

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN

from handlers.common_handlers import cancel, error_handler
from handlers.conversation_handlers import (
    get_selected_info_options,
    get_url,
    get_selected_playlist_videos,
    start,
)
from handlers.extra_commands_handlers import get_send_info, get_send_thumbnail
from handlers.help_handlers import help, help_commands, help_infos, help_url

from utils.bot_data import (
    PROVIDE_URL,
    SELECT_VIDEOS,
    SELECT_INFO_OPTIONS,
    VIDEO_INFO_OPTIONS,
    PLAYLIST_INFO_OPTIONS,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_error_handler(error_handler)

    help_handlers = [
        CommandHandler("help", help),
        CommandHandler("help_url", help_url),
        CommandHandler("help_infos", help_infos),
        CommandHandler("help_commands", help_commands),
    ]

    extra_command_handlers = [
        CommandHandler("info", get_send_info, block=False),
        CommandHandler("thumbnail", get_send_thumbnail, block=False),
    ]

    ALL_OR_NONE_PATTERN = "^(all|none)$"
    INFO_OPTIONS_SELECTION_PATTERN = f"^({'|'.join(VIDEO_INFO_OPTIONS + PLAYLIST_INFO_OPTIONS + ['playlist hidden videos', 'toggle_all', 'select_different_videos', 'cancel', 'done'])})$"

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PROVIDE_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_url)],
            SELECT_VIDEOS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, get_selected_playlist_videos
                ),
                CallbackQueryHandler(
                    get_selected_playlist_videos, pattern=ALL_OR_NONE_PATTERN
                ),
            ],
            SELECT_INFO_OPTIONS: [
                CallbackQueryHandler(
                    get_selected_info_options,
                    pattern=INFO_OPTIONS_SELECTION_PATTERN,
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    for handler in help_handlers + extra_command_handlers + [conversation_handler]:
        application.add_handler(handler)

    application.run_polling()


if __name__ == "__main__":
    main()

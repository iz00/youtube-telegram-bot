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
    receive_option_selection,
    receive_url,
    receive_video_selection,
    start,
)
from handlers.extra_commands_handlers import get_send_info, get_send_thumbnail
from handlers.help_handlers import help, help_commands, help_infos, help_url
from utils.bot_data import (
    SELECT_OPTIONS,
    SELECT_VIDEOS,
    URL,
    VIDEO_OPTIONS,
    PLAYLIST_OPTIONS,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
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
            SELECT_OPTIONS: [
                CallbackQueryHandler(
                    receive_option_selection,
                    pattern=f"^({'|'.join(VIDEO_OPTIONS + PLAYLIST_OPTIONS + ['playlist hidden videos', 'done', 'cancel', 'select_videos', 'select_all'])})$",
                )
            ],
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

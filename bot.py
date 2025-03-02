import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from config import BOT_TOKEN

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


# TODO: validate and determine wheter video or playlist
async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.replace(" ", "")

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=f"URL received: {url}."
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
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(help_handler)
    application.add_handler(conv_handler)

    application.run_polling()

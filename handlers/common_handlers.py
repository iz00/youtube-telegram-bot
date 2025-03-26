import asyncio
from telegram import Update
from telegram.error import TimedOut
from telegram.ext import ContextTypes, ConversationHandler


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

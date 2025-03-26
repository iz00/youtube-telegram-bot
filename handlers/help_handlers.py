from telegram import Update
from telegram.ext import ContextTypes
from utils.format_helpers import escape_markdown_v2


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

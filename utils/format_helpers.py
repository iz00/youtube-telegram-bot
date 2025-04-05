"""
Provides formatting and parsing helper functions for user input and YouTube data.

Includes:
- Parsing of user video selection input (e.g., "2, 4-7, 9")
- Formatting of durations, dates, and video chapters
- Escaping of text for Telegram MarkdownV2
- Formatting of video/playlist information for displaying
- Splitting of long messages while preserving formatting
"""

import re

from datetime import datetime


def parse_videos_selection(selection: str, video_count: int) -> list[int] | None:
    """Converts a user input selection string (e.g., "2, 4-7, 9") into a list of valid indices."""
    indices = set()
    try:
        parts = selection.split(",")
        for part in parts:
            if "-" in part:
                start, end = map(int, part.split("-"))
                if start > end or start < 1 or end > video_count:
                    return None
                indices.update(range(start, end + 1))
            else:
                index = int(part)
                if index < 1 or index > video_count:
                    return None
                indices.add(index)
    except ValueError:
        return None

    return sorted(indices)


def format_seconds(seconds: str) -> str:
    """Convert seconds into hh:mm:ss or mm:ss format."""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return (
        f"{hours:02}:{minutes:02}:{seconds:02}"
        if hours
        else f"{minutes:02}:{seconds:02}"
    )


def format_date(date: str) -> str:
    """Convert date from YYYYMMDD to MM/DD/YYYY format."""
    try:
        return f"{datetime.strptime(date, '%Y%m%d').strftime('%m/%d/%Y')} (mm/dd/yyyy)"
    except ValueError:
        return date


def format_video_urls(video_urls: list[str], max_videos_display: int = 10) -> str:
    """Formats a list of video URLs into a message."""
    formatted_video_urls = "\n".join(
        f"• {url}" for url in video_urls[:max_videos_display]
    )

    if (remaining_videos_quantity := len(video_urls) - max_videos_display) > 0:
        formatted_video_urls += f"\n... And {remaining_videos_quantity} more video{'s' if remaining_videos_quantity > 1 else ''}."

    return formatted_video_urls


def escape_markdown_v2(text: str) -> str:
    """Escapes special characters for Telegram MarkdownV2."""
    special_characters = r"_*\[\]()~`>#+\-=|{}.!\\"
    return re.sub(f"([{re.escape(special_characters)}])", r"\\\1", str(text))


def format_video_chapters(chapters: list[dict[str, str]]) -> list[str]:
    """Formats a list of video chapters dictionaries into a list of video chapters strings."""
    return [
        f"{chapter['title']} ({format_seconds(chapter['start_time'])} - {format_seconds(chapter['end_time'])})"
        for chapter in chapters
    ]


def format_infos(infos: dict[str, str], selected_info_options: list[str]) -> str:
    """Formats playlist or video infos into a message."""
    if not infos:
        return f"⚠️ {escape_markdown_v2('Error fetching infos. Please try again.')}"

    formatted_infos = []
    for option in selected_info_options:
        if option in infos and infos[option]:
            option_name = option.title()

            match option:
                case "duration":
                    option_value = format_seconds(infos[option])
                case "upload date":
                    option_value = format_date(infos[option])
                case "chapters" | "playlist hidden videos":
                    option_value = "\n" + "\n".join(
                        format_video_chapters(infos[option])
                        if option == "chapters"
                        else infos[option]
                    )
                case (
                    "title"
                    | "playlist title"
                    | "description"
                    | "playlist description"
                    | "uploader"
                    | "playlist uploader"
                    | "thumbnail"
                ):
                    option_value = f"\n{infos[option]}"
                case _:
                    option_value = infos[option]

            formatted_infos.append(
                f"*{option_name}:* {escape_markdown_v2(option_value)}"
            )

    return (
        "\n\n".join(formatted_infos)
        if formatted_infos
        else f"⚠️ {escape_markdown_v2('No infos available. Please try again.')}"
    )


def split_message(message: str, chunk_size: int = 4096) -> list[str]:
    """Splits a long message into smaller chunks, prioritizing newlines and preserving MarkdownV2 formatting."""
    chunks = []

    while message:
        if len(message) <= chunk_size:
            chunks.append(message)
            break

        # Try to split at the last newline within chunk_size
        split_position = message.rfind("\n", 0, chunk_size)

        # If no newline found, find a space instead
        if split_position == -1:
            split_position = message.rfind(" ", 0, chunk_size)

            # If no space found, force split at chunk_size
            if split_position == -1:
                split_position = chunk_size

        chunk = message[:split_position]

        # Ensure no split in the middle of a MarkdownV2 entity
        open_bold = chunk.count("*") % 2 != 0
        open_italic = chunk.count("_") % 2 != 0
        open_bolditalic = chunk.count("***") % 2 != 0

        if open_bold or open_italic or open_bolditalic:
            if safe_split := re.search(r"([*_]+)", chunk[::-1]):
                split_position -= safe_split.start() + 1
                chunk = message[:split_position]

        chunks.append(chunk.strip())
        message = message[split_position:].lstrip()

    return chunks

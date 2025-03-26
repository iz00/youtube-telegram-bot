import re
from datetime import datetime


def parse_video_selection(selection: str, max_length: int) -> list[int] | None:
    """Converts a user input string (e.g., "2, 4-7, 9") into a list of valid indices."""
    indices = set()
    try:
        parts = selection.split(",")
        for part in parts:
            if "-" in part:
                start, end = map(int, part.split("-"))
                if start > end or start < 1 or end > max_length:
                    return None
                indices.update(range(start, end + 1))
            else:
                index = int(part)
                if index < 1 or index > max_length:
                    return None
                indices.add(index)
    except ValueError:
        return None

    return sorted(indices)


def format_seconds(seconds: int) -> str:
    """Convert seconds into hh:mm:ss or mm:ss format."""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours:02}:{minutes:02}:{seconds:02}"  # hh:mm:ss
    return f"{minutes:02}:{seconds:02}"  # mm:ss


def format_date(date: str) -> str:
    """Convert date from YYYYMMDD to DD/MM/YYYY format."""
    try:
        return f"{datetime.strptime(date, '%Y%m%d').strftime('%m/%d/%Y')} (mm/dd/yyyy)"
    except ValueError:
        return date


def format_videos_urls(videos_urls: list[str], limit: int = 10) -> str:
    """Formats a list of video URLs into a message."""
    formatted_videos_urls = "\n".join(f"• {url}" for url in videos_urls[:limit])
    if len(videos_urls) > limit:
        formatted_videos_urls += f"\n... And another {len(videos_urls) - limit} videos."

    return formatted_videos_urls


def escape_markdown_v2(text: str) -> str:
    """Escapes special characters for Telegram Markdown V2."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", str(text))


def format_infos(info: dict[str, str], selected_options: list[str]) -> str:
    """Formats playlist or video infos into a message."""
    if not info:
        return "Error fetching infos."

    infos = []
    for option in selected_options:
        if option in info and info[option]:
            option_name = option.title()

            match option:
                case "duration":
                    option_value = format_seconds(info[option])
                case "upload date":
                    option_value = format_date(info[option])
                case (
                    "title"
                    | "playlist title"
                    | "description"
                    | "playlist description"
                    | "uploader"
                    | "playlist uploader"
                    | "thumbnail"
                ):
                    option_value = f"\n{info[option]}"
                case "chapters" | "playlist hidden videos":
                    option_value = "\n" + "\n".join(info[option])
                case _:
                    option_value = info[option]

            option_value = escape_markdown_v2(option_value)
            infos.append(f"*{option_name}:* {option_value}")

    return "\n\n".join(infos) if infos else "No infos available."


def split_message(message: str, chunk_size: int = 4096) -> list[str]:
    """Splits a long message into smaller chunks, prioritizing newlines and preserving Markdown formatting."""
    chunks = []

    while message:
        if len(message) <= chunk_size:
            chunks.append(message)
            break

        # Try to split at the last newline within chunk_size
        split_pos = message.rfind("\n", 0, chunk_size)

        # If no newline found, find a space instead
        if split_pos == -1:
            split_pos = message.rfind(" ", 0, chunk_size)

        # Force split at chunk_size
        if split_pos == -1:
            split_pos = chunk_size

        chunk = message[:split_pos]

        # Ensure don't split in the middle of a Markdown entity
        open_bold = chunk.count("*") % 2 != 0
        open_italic = chunk.count("_") % 2 != 0
        open_bolditalic = chunk.count("***") % 2 != 0

        if open_bold or open_italic or open_bolditalic:
            safe_split = re.search(r"([*_]+)", chunk[::-1])
            if safe_split:
                split_pos -= safe_split.start() + 1
                chunk = message[:split_pos]

        chunks.append(chunk.strip())
        message = message[split_pos:].lstrip()

    return chunks

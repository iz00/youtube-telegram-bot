import re, yt_dlp, requests
from datetime import datetime
from io import BytesIO
from PIL import Image
from config import YOUTUBE_API_KEY


def is_valid_youtube_url_format(url):
    """Returns True if the URL is a valid YouTube video, shorts, or playlist URL.
    Considers the video ID to have always 11 characters."""
    pattern = r"""
        ^(?:https?://)?                  # Optional https
        (?:
            (?:www\.|m\.)?youtube\.com   # Optional www. or m. subdomains
            /(?:
                watch                    # Video URLs
                (?:\?.*?)?               # Optional extra parameters before v or list
                (?=.*[?&]v=([\w-]{11}))  # Video ID (v=) required somewhere
                (?:[?&][\w-]+=[\w-]*)*   # Optional extra parameters
            |
                shorts/([\w-]{11})       # Shorts URLs
                (?:\?.*)?                # Optional extra parameters
            |
                playlist\?               # Playlist URLs
                (?:[?&]?list=([\w-]+))   # Playlist ID (list=) required somewhere
                (?:[?&][\w-]+=[\w-]*)*   # Optional extra parameters
            )
        |
            youtu\.be/([\w-]{11})        # Shortened URLs
            (?:\?.*)?                    # Optional extra parameters
        )
        $"""

    pattern = re.compile(pattern, re.VERBOSE | re.IGNORECASE)
    return bool(pattern.match(url))


def get_type_id_url(url):
    """Get the type and ID of YouTube URL.
    Type is either "playlist" or "video"."""
    if "playlist" in url:
        playlist_pattern = r"[?&]list=([a-zA-Z0-9_-]+)"
        playlist_match = re.search(playlist_pattern, url)
        if playlist_match:
            return {"type": "playlist", "id": playlist_match.group(1)}

    video_pattern = r"(?:youtube\.com\/(?:[^\/]+\/[^\/]+\/|(?:v|shorts)\/|.*[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
    video_match = re.search(video_pattern, url)
    if video_match:
        return {"type": "video", "id": video_match.group(1)}

    return {"error": "Invalid URL."}


def get_videos_urls(type, id):
    """
    Validate YouTube video or playlist ID and return a list of video URLs.
    - If the ID is invalid, return an empty list.
    - If it's a video, return [video URL] (unless video is blocked or unavailable).
    - If it's a playlist, return all available video URLs (even blocked or unavailable ones).
    """
    url = f"https://www.youtube.com/{'watch?v=' + id if type == 'video' else 'playlist?list=' + id}"

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,  # Only get URLs, no extra info
        "force_generic_extractor": True,  # Prevents unnecessary API calls
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if type == "video":
            return [info["webpage_url"]] if "webpage_url" in info else []
        elif type == "playlist":
            return [entry["url"] for entry in info.get("entries", []) if "url" in entry]

    except yt_dlp.utils.DownloadError:
        return []

    return []


def is_video_available(video_url):
    """Returns True if the video is available (not hidden, blocked, removed or private)."""
    ydl_opts = {
        "quiet": True,
        "noprogress": True,
        "extract_flat": True,
        "force_generic_extractor": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(video_url, download=False)
        return True
    except yt_dlp.utils.DownloadError:
        return False


def get_hidden_playlist_videos(videos_urls):
    """Return a list of video URLs that are hidden/unavailable in a playlist."""
    hidden_videos = []

    for url in videos_urls:
        if not is_video_available(url):
            hidden_videos.append(url)

    return hidden_videos


def parse_video_selection(selection, max_length):
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


def format_seconds(seconds):
    """Convert seconds into hh:mm:ss or mm:ss format."""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours:02}:{minutes:02}:{seconds:02}"  # hh:mm:ss
    return f"{minutes:02}:{seconds:02}"  # mm:ss


def format_date(date):
    """Convert date from YYYYMMDD to DD/MM/YYYY format."""
    try:
        return f"{datetime.strptime(date, '%Y%m%d').strftime('%m/%d/%Y')} (mm/dd/yyyy)"
    except ValueError:
        return date


def get_video_infos(url):
    """Fetches video metadata using yt_dlp and returns a dictionary."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "force_generic_extractor": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError:
        return None

    uploader_info = info.get("uploader")
    uploader = (
        f"{uploader_info} ({info.get('uploader_url')})" if uploader_info else None
    )

    chapters_info = info.get("chapters")
    chapters = (
        [
            f"{chapter['title']} ({format_seconds(chapter['start_time'])} - {format_seconds(chapter['end_time'])})"
            for chapter in chapters_info
        ]
        if chapters_info
        else None
    )

    return {
        "title": info.get("fulltitle"),
        "duration": info.get("duration"),
        "views count": info.get("view_count"),
        "likes count": info.get("like_count"),
        "comments count": info.get("comment_count"),
        "upload date": info.get("upload_date"),
        "uploader": uploader,
        "description": info.get("description"),
        "chapters": chapters,
        "thumbnail": info.get("thumbnail"),
    }


def get_playlist_infos(id):
    """Fetches playlist metadata using YouTube Data API v3 and returns a dictionary.
    yt_dlp is not used because if the playlist has any unavailable videos, it will raise an error.
    """
    url = f"https://www.googleapis.com/youtube/v3/playlists?part=snippet&id={id}&key={YOUTUBE_API_KEY}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching playlist info: {e}")
        return None

    if "items" not in data or not data["items"]:
        return None

    info = data["items"][0]["snippet"]
    uploader_info = info.get("channelId")

    # Get channel information through yt_dlp,
    # Because the YT Data API doesn't provide uploader's handle (@).
    if uploader_info:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
        }
        channel_url = f"https://www.youtube.com/channel/{uploader_info}"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                channel_info = ydl.extract_info(channel_url, download=False)
        except yt_dlp.utils.DownloadError as e:
            print(f"Error fetching channel info: {e}")
            uploader = None
        else:
            uploader_name = channel_info.get("channel")
            uploader_url = channel_info.get("uploader_url")
            uploader = f"{uploader_name} ({uploader_url})"

    return {
        "playlist title": info.get("title"),
        "playlist description": info.get("description"),
        "playlist uploader": uploader,
    }


def escape_markdown_v2(text):
    """Escapes special characters for Telegram Markdown V2."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", str(text))


def format_infos(info, selected_options):
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


def split_message(message, chunk_size=4096):
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


def process_image(image_data):
    """Converts an image to JPEG format."""
    try:
        image = Image.open(BytesIO(image_data))
        image = image.convert("RGB")
        new_image = BytesIO()
        image.save(new_image, format="JPEG")
        new_image.seek(0)
        return new_image
    except Exception as e:
        print(f"Error processing image: {e}")
        return None

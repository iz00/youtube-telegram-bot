"""
Provides helper functions for validating YouTube URLs and fetching metadata using yt_dlp and the YouTube Data API.

Includes:
- URL format validation and ID extraction.
- Detection of URL type (video or playlist).
- Fetching of video and playlist URLs, including detection of unavailable videos.
- Fetching of metadata for individual videos and playlists.
- Asynchronous support for efficient network-bound operations.
"""

import aiohttp, asyncio, re, yt_dlp

from config import YOUTUBE_API_KEY


def is_valid_youtube_url_format(url: str) -> bool:
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


def get_youtube_url_type(url: str) -> str | None:
    """Determine if a YouTube URL is a 'video' or 'playlist'."""
    if "playlist" in url and re.search(r"[?&]list=([a-zA-Z0-9_-]+)", url):
        return "playlist"

    if re.search(
        r"(?:youtube\.com\/(?:[^\/]+\/[^\/]+\/|(?:v|shorts)\/|.*[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})",
        url,
    ):
        return "video"

    return None


def get_youtube_url_id(url: str, yt_type: str) -> str | None:
    """Extract the ID from a YouTube URL based on the type ('video' or 'playlist')."""
    patterns = {
        "playlist": r"[?&]list=([a-zA-Z0-9_-]+)",
        "video": r"(?:youtube\.com\/(?:[^\/]+\/[^\/]+\/|(?:v|shorts)\/|.*[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})",
    }

    match = re.search(patterns.get(yt_type), url)

    return match.group(1) if match else None


async def get_videos_urls(type: str, id: str) -> list[str] | None:
    """
    Validate YouTube video or playlist ID and return a list of video URLs.
    - If the ID is invalid, return None.
    - If it's a video, return [video URL] (unless video is blocked or unavailable).
    - If it's a playlist, return all video URLs (even blocked or unavailable ones).
    """
    url = f"https://www.youtube.com/{'watch?v=' + id if type == 'video' else 'playlist?list=' + id}"

    yt_dlp_options = {
        "quiet": True,
        "extract_flat": True,  # Only get URLs, no extra info
        "force_generic_extractor": True,  # Prevents unnecessary API calls
        "cookiefile": "cookies.txt",
    }

    try:
        info = await asyncio.to_thread(
            lambda: yt_dlp.YoutubeDL(yt_dlp_options).extract_info(url, download=False)
        )

        if type == "video":
            return [info["webpage_url"]] if "webpage_url" in info else None
        elif type == "playlist":
            return [entry["url"] for entry in info.get("entries", []) if "url" in entry]

    except yt_dlp.utils.DownloadError:
        return None

    return None


async def is_video_available(video_url: str) -> bool:
    """Returns True if the video is available (not hidden, blocked, removed or private)."""
    yt_dlp_options = {
        "quiet": True,
        "noprogress": True,
        "extract_flat": True,
        "force_generic_extractor": True,
        "cookiefile": "cookies.txt",
    }

    try:
        await asyncio.to_thread(
            lambda: yt_dlp.YoutubeDL(yt_dlp_options).extract_info(
                video_url, download=False
            )
        )
        return True
    except yt_dlp.utils.DownloadError:
        return False


async def get_hidden_playlist_videos(
    videos_urls: list[str], cancel_event: asyncio.Event, max_concurrent_tasks: int = 10
) -> list[str]:
    """Return a list of video URLs that are hidden/unavailable in a playlist."""
    hidden_videos_urls = []

    async def process_batch(batch):
        if cancel_event.is_set():
            return

        tasks = [is_video_available(url) for url in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        if cancel_event.is_set():
            return

        hidden_videos_urls.extend(
            [batch[i] for i in range(len(batch)) if results[i] is False]
        )

    batches = [
        videos_urls[i : i + max_concurrent_tasks]
        for i in range(0, len(videos_urls), max_concurrent_tasks)
    ]

    for batch in batches:
        if cancel_event.is_set():
            return []
        await process_batch(batch)

    return hidden_videos_urls


async def get_video_infos(video_url: str) -> dict[str, str] | None:
    """Fetches video metadata using yt_dlp and returns a dictionary."""
    yt_dlp_options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "force_generic_extractor": False,
        "cookiefile": "cookies.txt",
    }

    try:
        info = await asyncio.to_thread(
            lambda: yt_dlp.YoutubeDL(yt_dlp_options).extract_info(
                video_url, download=False
            )
        )
    except yt_dlp.utils.DownloadError:
        return None

    if uploader := info.get("uploader"):
        uploader_url = info.get("uploader_url")
        uploader = f"{uploader} ({uploader_url})" if uploader_url else uploader

    return {
        "title": info.get("fulltitle"),
        "duration": info.get("duration"),
        "views count": info.get("view_count"),
        "likes count": info.get("like_count"),
        "comments count": info.get("comment_count"),
        "upload date": info.get("upload_date"),
        "uploader": uploader,
        "description": info.get("description"),
        "chapters": info.get("chapters"),
        "thumbnail": info.get("thumbnail"),
    }


async def get_channel_infos(channel_id: str) -> str | None:
    """Fetches channel name and url with handle (@) using yt_dlp, provided the channel id."""
    channel_url_with_id = f"https://www.youtube.com/channel/{channel_id}"

    yt_dlp_options = {
        "quiet": True,
        "extract_flat": True,
        "cookiefile": "cookies.txt",
    }

    try:
        info = await asyncio.to_thread(
            lambda: yt_dlp.YoutubeDL(yt_dlp_options).extract_info(
                channel_url_with_id, download=False
            )
        )
    except yt_dlp.utils.DownloadError as e:
        print(f"Error fetching channel {channel_url} info: {e}")
        return None
    else:
        if channel_name := info.get("channel"):
            channel_url = info.get("uploader_url")
            return f"{channel_name} ({channel_url})" if channel_url else channel_name


async def get_playlist_infos(playlist_id: str) -> dict[str, str] | None:
    """Fetches playlist metadata using YouTube Data API v3 and returns a dictionary.
    yt_dlp is not used because if the playlist has any unavailable videos, it will raise an error.
    """
    url = f"https://www.googleapis.com/youtube/v3/playlists?part=snippet&id={playlist_id}&key={YOUTUBE_API_KEY}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
    except aiohttp.ClientError as e:
        print(f"Error fetching playlist info: {e}")
        return None

    if "items" not in data or not data["items"]:
        return None

    info = data["items"][0]["snippet"]

    # Get channel information through yt_dlp,
    # Because the YT Data API doesn't provide uploader's handle (@).
    if uploader := info.get("channelId"):
        uploader = await get_channel_infos(uploader)

    return {
        "playlist title": info.get("title"),
        "playlist description": info.get("description"),
        "playlist uploader": uploader,
    }

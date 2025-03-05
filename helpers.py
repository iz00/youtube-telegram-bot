import re, yt_dlp


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

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

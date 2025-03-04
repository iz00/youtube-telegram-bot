import re, requests
from os import getenv

YOUTUBE_API_KEY = getenv("YOUTUBE_API_KEY")

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


def get_videos_ids(type, id):
    """
    Validate YouTube video or playlist ID and return a list of video IDs.
    - If the ID is invalid, return an empty list.
    - If it's a video, return [video_id].
    - If it's a playlist, return all video IDs in the playlist.
    """
    if type == "video":
        url = f"https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "status",
            "id": id,
            "key": YOUTUBE_API_KEY,
        }
    elif type == "playlist":
        url = "https://www.googleapis.com/youtube/v3/playlistItems"
        params = {
            "part": "contentDetails",
            "playlistId": id,
            "maxResults": 50,
            "key": YOUTUBE_API_KEY,
        }
    else:
        return []

    video_ids = []
    next_page_token = None

    while True:
        response = requests.get(url, params=params)
        data = response.json()

        # Invalid video or playlist
        if not data.get("items"):
            return []

        if type == "video":
            return [id]

        for item in data["items"]:
            video_ids.append(item["contentDetails"]["videoId"])

        # Check for more pages, API only gets 50 videos at a time
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
        params["pageToken"] = next_page_token

    return video_ids

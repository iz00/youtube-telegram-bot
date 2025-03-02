import re


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

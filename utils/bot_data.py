# ConversationHandler states
URL, SELECT_VIDEOS, SELECT_OPTIONS = range(3)

# Options available to users
VIDEO_OPTIONS = [
    "title",
    "duration",
    "views count",
    "likes count",
    "comments count",
    "upload date",
    "uploader",
    "description",
    "chapters",
    "thumbnail",
]
PLAYLIST_OPTIONS = [
    "playlist title",
    "playlist description",
    "playlist uploader",
]

# Options that have statistics
OPTIONS_WITH_STATS = [
    "duration",
    "views count",
    "likes count",
    "comments count",
]

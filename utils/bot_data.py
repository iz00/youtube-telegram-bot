# ConversationHandler states
PROVIDE_URL, SELECT_VIDEOS, SELECT_INFO_OPTIONS = range(3)

# Info options available to users
VIDEO_INFO_OPTIONS = [
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
PLAYLIST_INFO_OPTIONS = [
    "playlist title",
    "playlist description",
    "playlist uploader",
]

# Info options that have statistics
STATISTICAL_INFO_OPTIONS = [
    "duration",
    "views count",
    "likes count",
    "comments count",
]

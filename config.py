"""
Loads environment variables used for bot configuration and API key for data fetching.

These variables should be set in environment before running the bot.
"""

from os import getenv

BOT_TOKEN = getenv("BOT_TOKEN")
YOUTUBE_API_KEY = getenv("YOUTUBE_API_KEY")

# File for configuration variables

from os import getenv
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

BOT_TOKEN = getenv("BOT_TOKEN")

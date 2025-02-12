# config.py
import os
from dotenv import load_dotenv
from telegram.ext import filters

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
PROXY_API_KEY = os.getenv('PROXY_API_KEY')

DB_PATH = "bot_storage.db"
DEFAULT_INSTRUCTIONS = ""

AVAILABLE_MODELS = ["gpt-4o", "o1"]

TIMEOUT_CONFIG = dict(
    connect=10.0,
    read=60.0,
    write=10.0,
    pool=5.0
)

# Параметры Telegram
MAX_TELEGRAM_TEXT = 4000
PAGE_SIZE = 5
TRUNCATE_SUFFIX = "\n[...текст обрезан...]"

# Состояния ConversationHandler
SET_INSTRUCTIONS = 1
SET_NEW_CHAT_TITLE = 2
SET_RENAME_CHAT = 3

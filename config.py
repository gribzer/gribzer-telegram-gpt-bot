# config.py
import os
import httpx
from dotenv import load_dotenv
from telegram.ext import filters

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
PROXY_API_KEY = os.getenv('PROXY_API_KEY')

DB_PATH = "bot_storage.db"
DEFAULT_INSTRUCTIONS = ""

AVAILABLE_MODELS = ["gpt-4o", "o3-mini"]

HEADERS = {
    "Content-Type": "application/json"
}
HEADERS_P = {
    "Content-Type": "application/json"
}
HEADERS_T = {
    "Content-Type": "application/json"
}

TIMEOUT_CONFIG = dict(
    connect=10,
    read=60,
    write=20,
    pool=10
)

# Новый объект Timeout
TIMEOUT = httpx.Timeout(**TIMEOUT_CONFIG)

# Параметры Telegram
MAX_TELEGRAM_TEXT = 4000
PAGE_SIZE = 5
TRUNCATE_SUFFIX = "\n[...текст обрезан...]"

# Состояния ConversationHandler
SET_INSTRUCTIONS = 1
SET_NEW_CHAT_TITLE = 2
SET_RENAME_CHAT = 3

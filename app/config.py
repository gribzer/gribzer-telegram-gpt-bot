import os
from dotenv import load_dotenv
import httpx

load_dotenv()  # Загружаем переменные из .env (TELEGRAM_TOKEN, DB_URL и т.д.)

# ========== Телеграм / Proxy API ==========
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
PROXY_API_KEY = os.getenv('PROXY_API_KEY')

# ========== T-Касса / Tinkoff ==========
T_KASSA_TERMINAL = os.getenv("T_KASSA_TERMINAL", "")
T_KASSA_SECRET_KEY = os.getenv("T_KASSA_SECRET_KEY", "")
T_KASSA_PASSWORD = os.getenv("T_KASSA_PASSWORD", "")
T_KASSA_API_URL = os.getenv("T_KASSA_API_URL", "https://securepay.tinkoff.ru/v2")
T_KASSA_IS_TEST = os.getenv("T_KASSA_IS_TEST", "False").lower() == "true"

# ========== База данных ==========
# Пример: "sqlite+aiosqlite:///./bot_storage.db"
# или "postgresql+asyncpg://username:pass@host:5432/dbname"
DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///./bot_storage.db")

# ========== Настройки OpenAI Proxy (если нужно) ==========
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {PROXY_API_KEY}" if PROXY_API_KEY else ""
}

TIMEOUT_CONFIG = dict(connect=10, read=60, write=20, pool=10)
TIMEOUT = httpx.Timeout(**TIMEOUT_CONFIG)

# ========== Разные константы для Telegram-бота ==========
MAX_TELEGRAM_TEXT = 4000
PAGE_SIZE = 5
TRUNCATE_SUFFIX = "\n[...текст обрезан...]"

# Состояния ConversationHandler (если вы используете PTB ConversationHandler)
SET_INSTRUCTIONS = 1
SET_NEW_CHAT_TITLE = 2
SET_RENAME_CHAT = 3

DEFAULT_INSTRUCTIONS = ""

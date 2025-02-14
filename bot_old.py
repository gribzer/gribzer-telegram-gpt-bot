import os
import re
import logging
import sqlite3
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
import httpx
from dotenv import load_dotenv
from telegram.error import BadRequest

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
PROXY_API_KEY = os.getenv('PROXY_API_KEY')

DB_PATH = "bot_storage.db"
DEFAULT_INSTRUCTIONS = ""

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния
SET_INSTRUCTIONS = 1
SET_NEW_CHAT_TITLE = 2
SET_RENAME_CHAT = 3

AVAILABLE_MODELS = ["gpt-4o", "o3-mini"]
TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0)

PAGE_SIZE = 5  # Кол-во сообщений на страницу (числом)
MAX_TELEGRAM_TEXT = 4000  # Лимит для edit_message_text (с запасом)
TRUNCATE_SUFFIX = "\n[...текст обрезан...]"


# -------------------------------------------------------------------------
#  ИНИЦИАЛИЗАЦИЯ БД
# -------------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Таблица users
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            selected_model TEXT,
            instructions TEXT,
            active_chat_id INTEGER
        )
    ''')
    # Таблица чатов
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            is_favorite INTEGER DEFAULT 0
        )
    ''')
    # Таблица сообщений
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            role TEXT,
            content TEXT
        )
    ''')
    conn.commit()
    conn.close()

def upgrade_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # user_chats: поле is_favorite
    c.execute("PRAGMA table_info(user_chats)")
    columns = [row[1] for row in c.fetchall()]
    if "is_favorite" not in columns:
        c.execute("ALTER TABLE user_chats ADD COLUMN is_favorite INTEGER DEFAULT 0")
        conn.commit()

    # users: instructions, active_chat_id
    c.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in c.fetchall()]
    if "instructions" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN instructions TEXT")
        conn.commit()
    if "active_chat_id" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN active_chat_id INTEGER")
        conn.commit()

    conn.close()

# -------------------------------------------------------------------------
#  ФУНКЦИИ РАБОТЫ С БД
# -------------------------------------------------------------------------
def get_user_model(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT selected_model FROM users WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_user_model(chat_id: int, model: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    existing = get_user_model(chat_id)
    if existing is None:
        c.execute(
            "INSERT INTO users (chat_id, selected_model, instructions, active_chat_id) VALUES (?, ?, ?, ?)",
            (chat_id, model, DEFAULT_INSTRUCTIONS, None)
        )
    else:
        c.execute("UPDATE users SET selected_model=? WHERE chat_id=?", (model, chat_id))
    conn.commit()
    conn.close()

def get_user_instructions(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT instructions FROM users WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else None

def set_user_instructions(chat_id: int, instructions: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if get_user_model(chat_id) is None:
        c.execute(
            "INSERT INTO users (chat_id, selected_model, instructions, active_chat_id) VALUES (?, ?, ?, ?)",
            (chat_id, "gpt-3.5-turbo", instructions, None)
        )
    else:
        c.execute("UPDATE users SET instructions=? WHERE chat_id=?", (instructions, chat_id))
    conn.commit()
    conn.close()

def get_active_chat_id(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT active_chat_id FROM users WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_active_chat_id(chat_id: int, active_chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET active_chat_id=? WHERE chat_id=?", (active_chat_id, chat_id))
    conn.commit()
    conn.close()

# Чаты
def create_new_chat(chat_id: int, title: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if get_user_model(chat_id) is None:
        c.execute(
            "INSERT INTO users (chat_id, selected_model, instructions, active_chat_id) VALUES (?, ?, ?, ?)",
            (chat_id, "gpt-3.5-turbo", DEFAULT_INSTRUCTIONS, None)
        )
        conn.commit()

    c.execute("INSERT INTO user_chats (user_id, title, is_favorite) VALUES (?, ?, 0)", (chat_id, title))
    new_chat_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_chat_id

def get_user_chats(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, is_favorite FROM user_chats WHERE user_id=?", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_favorite_chats(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, is_favorite FROM user_chats WHERE user_id=? AND is_favorite=1", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def delete_chat(chat_db_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM chat_messages WHERE chat_id=?", (chat_db_id,))
    c.execute("DELETE FROM user_chats WHERE id=?", (chat_db_id,))
    conn.commit()
    conn.close()

def rename_chat(chat_db_id: int, new_title: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE user_chats SET title=? WHERE id=?", (new_title, chat_db_id))
    conn.commit()
    conn.close()

def set_chat_favorite(chat_db_id: int, is_fav: bool):
    val = 1 if is_fav else 0
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE user_chats SET is_favorite=? WHERE id=?", (val, chat_db_id))
    conn.commit()
    conn.close()

def get_chat_title_by_id(chat_db_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT title FROM user_chats WHERE id=?", (chat_db_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# Сообщения
def add_message_to_chat(chat_db_id: int, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO chat_messages (chat_id, role, content) VALUES (?, ?, ?)", (chat_db_id, role, content))
    conn.commit()
    conn.close()

def get_chat_messages(chat_db_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content FROM chat_messages WHERE chat_id=? ORDER BY id ASC", (chat_db_id,))
    rows = c.fetchall()
    conn.close()
    messages = [{"role": row[0], "content": row[1]} for row in rows]
    return messages

# -------------------------------------------------------------------------
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# -------------------------------------------------------------------------
def partial_escape_markdown_v2(text: str) -> str:
    special_chars = r'\[\]\(\)~`>#\+\-=|{}\.!'
    pattern = f'([{re.escape(special_chars)}])'
    return re.sub(pattern, r'\\\1', text)

def convert_to_telegram_markdown_v2(text: str) -> str:
    pattern = r"(```[\s\S]+?```|`[^`]+`)"
    segments = re.split(pattern, text)
    for i, segment in enumerate(segments):
        if not (segment.startswith("```") or (segment.startswith("`") and segment.endswith("`"))):
            segments[i] = partial_escape_markdown_v2(segment)
    return "".join(segments)

def truncate_if_too_long(text: str, limit: int = MAX_TELEGRAM_TEXT) -> str:
    """
    Если текст превышает лимит, обрежем и добавим суффикс [...].
    """
    if len(text) <= limit:
        return text
    else:
        return text[: limit - len(TRUNCATE_SUFFIX)] + TRUNCATE_SUFFIX


# -------------------------------------------------------------------------
#  /start
# -------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Меню"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    welcome_text = (
        "Привет! Я бот, использующий Proxy API для ChatGPT.\n"
        "Нажмите кнопку «Меню», чтобы увидеть настройки и инструкции."
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)


# -------------------------------------------------------------------------
#  ГЛАВНОЕ МЕНЮ
# -------------------------------------------------------------------------
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = (update.message.chat.id if update.message else update.callback_query.message.chat.id)
    active_id = get_active_chat_id(chat_id)
    model_name = get_user_model(chat_id) or "—"
    all_chats = get_user_chats(chat_id)
    total_chats = len(all_chats)

    if active_id:
        active_title = get_chat_title_by_id(active_id) or f"(ID {active_id})"
    else:
        active_title = "не выбран"

    main_text = (
        f"Текущий чат: {active_title}\n"
        f"Модель: {model_name}\n"
        f"Всего чатов: {total_chats}\n"
    )

    keyboard = [
        [InlineKeyboardButton("📑 Все чаты", callback_data="all_chats")],
        [InlineKeyboardButton("⭐ Избранные чаты", callback_data="favorite_chats")],
        [InlineKeyboardButton("🤖 Сменить модель", callback_data="change_model")],
        [InlineKeyboardButton("📝 Инструкции", callback_data="update_instructions")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(main_text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(main_text, reply_markup=reply_markup)


# -------------------------------------------------------------------------
#  СПИСКИ ЧАТОВ: "Все" и "Избранные"
# -------------------------------------------------------------------------
async def show_all_chats_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.message.chat.id
    all_chats = get_user_chats(user_id)

    if not all_chats:
        text = "У вас пока нет ни одного чата."
        keyboard = [
            [InlineKeyboardButton("Создать новый чат", callback_data="new_chat")],
            [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text_lines = ["Ваши чаты:\n"]
    keyboard = []
    for (db_id, title, is_fav) in all_chats:
        prefix = "⭐ " if is_fav else ""
        text_lines.append(f"• ID {db_id}: {prefix}{title}")
        keyboard.append([InlineKeyboardButton(f"{prefix}{title}", callback_data=f"open_chat_{db_id}")])

    text_result = "\n".join(text_lines)
    keyboard.append([InlineKeyboardButton("Создать новый чат", callback_data="new_chat")])
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")])

    await query.edit_message_text(text_result, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_favorite_chats_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.message.chat.id
    fav_chats = get_favorite_chats(user_id)

    if not fav_chats:
        text = "У вас нет избранных чатов."
        keyboard = [
            [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text_lines = ["Избранные чаты:\n"]
    keyboard = []
    for (db_id, title, is_fav) in fav_chats:
        prefix = "⭐ "
        text_lines.append(f"• ID {db_id}: {prefix}{title}")
        keyboard.append([InlineKeyboardButton(f"{prefix}{title}", callback_data=f"open_chat_{db_id}")])

    text_result = "\n".join(text_lines)
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")])

    await query.edit_message_text(text_result, reply_markup=InlineKeyboardMarkup(keyboard))


# -------------------------------------------------------------------------
#  ПОД-МЕНЮ ОТДЕЛЬНОГО ЧАТА
# -------------------------------------------------------------------------
async def show_single_chat_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_db_id: int):
    query = update.callback_query
    chat_title = get_chat_title_by_id(chat_db_id)
    if not chat_title:
        await query.edit_message_text("Чат не найден (возможно, удалён).", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="all_chats")]
        ]))
        return

    # Проверяем, избранный ли чат
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT is_favorite FROM user_chats WHERE id=?", (chat_db_id,))
    row = c.fetchone()
    conn.close()
    is_fav = (row and row[0] == 1)

    favorite_btn_text = "Убрать из избранного" if is_fav else "Добавить в избранное"
    favorite_cb = f"unfav_{chat_db_id}" if is_fav else f"fav_{chat_db_id}"

    text = f"Чат: {chat_title}\nID: {chat_db_id}\n\nВыберите действие:"
    keyboard = [
        [InlineKeyboardButton("Назначить активным", callback_data=f"set_active_{chat_db_id}")],
        [InlineKeyboardButton("Переименовать", callback_data=f"rename_{chat_db_id}")],
        [InlineKeyboardButton("История", callback_data=f"history_{chat_db_id}:page_0")],
        [InlineKeyboardButton(favorite_btn_text, callback_data=favorite_cb)],
        [InlineKeyboardButton("Удалить", callback_data=f"delete_chat_{chat_db_id}")],
        [InlineKeyboardButton("🔙 Назад к списку", callback_data="all_chats")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# -------------------------------------------------------------------------
#  ПРОСМОТР ИСТОРИИ ЧАТА
# -------------------------------------------------------------------------
async def show_chat_history(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_db_id: int, page: int):
    """
    Показываем сообщения чата, разбитые на страницы (PAGE_SIZE).
    Дополнительно обрезаем сообщение, если оно всё равно длиннее ~4000 символов.
    """
    query = update.callback_query
    messages = get_chat_messages(chat_db_id)
    total_messages = len(messages)

    start_index = page * PAGE_SIZE
    end_index = start_index + PAGE_SIZE
    page_messages = messages[start_index:end_index]

    if not page_messages:
        # Если страница пуста, откатываем на предыдущую или сообщаем
        if page > 0:
            return await show_chat_history(update, context, chat_db_id, page - 1)
        else:
            await query.edit_message_text(
                "В этом чате нет сообщений.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data=f"open_chat_{chat_db_id}")]
                ])
            )
            return

    text_lines = [f"История чата {chat_db_id}, страница {page + 1}"]
    for i, msg in enumerate(page_messages, start=start_index + 1):
        role_emoji = "👤" if msg["role"] == "user" else "🤖"
        text_lines.append(f"{i}) {role_emoji} {msg['role']}: {msg['content']}")

    text_result = "\n".join(text_lines)
    # Если слишком длинно — обрежем
    text_result = truncate_if_too_long(text_result, MAX_TELEGRAM_TEXT)

    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("◀️", callback_data=f"history_{chat_db_id}:page_{page-1}"))
    if end_index < total_messages:
        buttons.append(InlineKeyboardButton("▶️", callback_data=f"history_{chat_db_id}:page_{page+1}"))

    buttons.append(InlineKeyboardButton("🔙 Назад", callback_data=f"open_chat_{chat_db_id}"))

    reply_markup = InlineKeyboardMarkup([buttons])
    await query.edit_message_text(text_result, reply_markup=reply_markup)


# -------------------------------------------------------------------------
#  СОЗДАНИЕ НОВОГО ЧАТА (ConversationHandler)
# -------------------------------------------------------------------------
async def new_chat_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите название нового чата (или /cancel для отмены):")
    return SET_NEW_CHAT_TITLE

async def set_new_chat_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if user_text.startswith("/cancel"):
        await update.message.reply_text("Создание чата отменено.")
        await menu(update, context)
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    new_chat_id = create_new_chat(chat_id, user_text)
    set_active_chat_id(chat_id, new_chat_id)

    await update.message.reply_text(
        f"Чат создан и выбран в качестве активного! (ID: {new_chat_id})"
    )
    # Возвращаемся в меню
    await menu(update, context)
    return ConversationHandler.END


# -------------------------------------------------------------------------
#  ПЕРЕИМЕНОВАНИЕ ЧАТА (ConversationHandler)
# -------------------------------------------------------------------------
async def rename_chat_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_db_id = int(data.split("_")[-1])
    context.user_data["rename_chat_id"] = chat_db_id

    await query.edit_message_text("Введите новое название чата (или /cancel для отмены):")
    return SET_RENAME_CHAT

async def rename_chat_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if user_text.lower() == "/cancel":
        await update.message.reply_text("Переименование отменено.")
        await menu(update, context)
        return ConversationHandler.END

    chat_db_id = context.user_data.get("rename_chat_id")
    if not chat_db_id:
        await update.message.reply_text("Не удалось найти чат для переименования.")
        await menu(update, context)
        return ConversationHandler.END

    rename_chat(chat_db_id, user_text)
    await update.message.reply_text(f"Чат {chat_db_id} переименован!")
    await menu(update, context)
    return ConversationHandler.END


# -------------------------------------------------------------------------
#  ОБНОВЛЕНИЕ ИНСТРУКЦИЙ (ConversationHandler)
# -------------------------------------------------------------------------
async def receive_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() in ["меню", "назад", "отмена", "/cancel"]:
        await update.message.reply_text("Обновление инструкций отменено.")
        await menu(update, context)
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    set_user_instructions(chat_id, text)
    await update.message.reply_text("Инструкции обновлены!")
    await menu(update, context)
    return ConversationHandler.END


# -------------------------------------------------------------------------
#  ОБРАБОТКА INLINE-КНОПОК
# -------------------------------------------------------------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_to_menu":
        await menu(update, context)
        return

    elif data == "all_chats":
        await show_all_chats_list(update, context)
        return

    elif data == "favorite_chats":
        await show_favorite_chats_list(update, context)
        return

    elif data == "new_chat":
        return await new_chat_entry(update, context)

    elif data == "change_model":
        keyboard = [[InlineKeyboardButton(model, callback_data=f"model_{model}")] for model in AVAILABLE_MODELS]
        keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")])
        await query.edit_message_text("Выберите модель:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif data.startswith("model_"):
        selected_model = data.split("_", 1)[1]
        chat_id = query.message.chat.id
        set_user_model(chat_id, selected_model)
        await query.edit_message_text(
            text=f"Выбрана модель: {selected_model}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]])
        )
        return

    elif data == "update_instructions":
        # Начинаем обновление инструкций (ConversationHandler)
        await query.edit_message_text(
            "Пожалуйста, отправьте новые инструкции (или /cancel для отмены):"
        )
        return SET_INSTRUCTIONS

    elif data == "help":
        text = (
            "❓ Помощь:\n"
            "1. Отправьте любое текстовое сообщение – бот ответит через Proxy API.\n"
            "2. «Все чаты» – список всех ваших чатов.\n"
            "3. «Избранные чаты» – только отмеченные ⭐.\n"
            "4. «Сменить модель» – сменить GPT-модель.\n"
            "5. «Инструкции» – задать системные инструкции.\n"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]])
        )
        return

    # --- Управление чатами ---
    elif data.startswith("open_chat_"):
        chat_db_id = int(data.split("_")[-1])
        await show_single_chat_menu(update, context, chat_db_id)
        return

    elif data.startswith("set_active_"):
        chat_db_id = int(data.split("_")[-1])
        user_id = query.message.chat.id
        set_active_chat_id(user_id, chat_db_id)
        await query.edit_message_text(
            text=f"Чат {chat_db_id} теперь активен.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]])
        )
        return

    elif data.startswith("rename_"):
        return await rename_chat_entry(update, context)

    elif data.startswith("delete_chat_"):
        chat_db_id = int(data.split("_")[-1])
        user_id = query.message.chat.id
        if get_active_chat_id(user_id) == chat_db_id:
            set_active_chat_id(user_id, None)
        delete_chat(chat_db_id)
        await query.edit_message_text(
            text=f"Чат {chat_db_id} удалён.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]])
        )
        return

    elif data.startswith("fav_"):
        chat_db_id = int(data.split("_")[-1])
        set_chat_favorite(chat_db_id, True)
        await show_single_chat_menu(update, context, chat_db_id)
        return

    elif data.startswith("unfav_"):
        chat_db_id = int(data.split("_")[-1])
        set_chat_favorite(chat_db_id, False)
        await show_single_chat_menu(update, context, chat_db_id)
        return

    elif data.startswith("history_"):
        # Пример: "history_10:page_0"
        parts = data.split(":")
        chat_part = parts[0].split("_")[-1]
        chat_db_id = int(chat_part)
        page = 0
        if len(parts) > 1 and parts[1].startswith("page_"):
            page = int(parts[1].split("_")[-1])
        await show_chat_history(update, context, chat_db_id, page)
        return

    # Если не распознали
    await query.edit_message_text(
        "Неизвестная команда.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]])
    )
    return ConversationHandler.END


# -------------------------------------------------------------------------
#  ОБРАБОТКА СООБЩЕНИЙ ОТ ПОЛЬЗОВАТЕЛЯ
# -------------------------------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    # "Меню"
    if user_text.lower() == "меню":
        await menu(update, context)
        return

    chat_id = update.effective_chat.id
    selected_model = get_user_model(chat_id)
    if selected_model is None:
        selected_model = "gpt-3.5-turbo"
        set_user_model(chat_id, selected_model)

    active_chat_db_id = get_active_chat_id(chat_id)
    if not active_chat_db_id:
        active_chat_db_id = create_new_chat(chat_id, "Новый чат")
        set_active_chat_id(chat_id, active_chat_db_id)

    chat_messages = get_chat_messages(active_chat_db_id)
    user_instructions = get_user_instructions(chat_id) or DEFAULT_INSTRUCTIONS

    messages_for_api = []
    if user_instructions.strip():
        messages_for_api.append({"role": "system", "content": user_instructions})
    for msg in chat_messages:
        messages_for_api.append({"role": msg["role"], "content": msg["content"]})
    messages_for_api.append({"role": "user", "content": user_text})

    add_message_to_chat(active_chat_db_id, "user", user_text)

    try:
        url = "https://api.proxyapi.ru/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {PROXY_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": selected_model,
            "messages": messages_for_api,
            "max_tokens": 500,
            "temperature": 0.2,
            "top_p": 1.0,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            answer = data["choices"][0]["message"]["content"]
    except httpx.ReadTimeout:
        logger.error("Время ожидания ответа от Proxy API истекло.", exc_info=True)
        answer = "Время ожидания ответа истекло, пожалуйста, повторите запрос позже."
    except Exception as e:
        logger.error(f"Ошибка при вызове Proxy API: {e}", exc_info=True)
        answer = "Произошла ошибка при обработке запроса."

    # Сохраняем ответ
    add_message_to_chat(active_chat_db_id, "assistant", answer)

    formatted_answer = convert_to_telegram_markdown_v2(answer)

    # УБИРАЕМ кнопку "В меню": ответ — без Inline-клавиатуры
    try:
        await update.message.reply_text(
            formatted_answer,
            parse_mode="MarkdownV2"
        )
    except BadRequest:
        logger.error("Ошибка при отправке с MarkdownV2, отправляем без форматирования", exc_info=True)
        await update.message.reply_text(answer)


# -------------------------------------------------------------------------
#  MAIN
# -------------------------------------------------------------------------
def main():
    init_db()
    upgrade_db()

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # ConversationHandler: инструкции
    instructions_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(lambda u,c: SET_INSTRUCTIONS, pattern="^update_instructions$")],
        states={
            SET_INSTRUCTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_instructions)
            ]
        },
        fallbacks=[],
        map_to_parent={},
    )

    # ConversationHandler: создание нового чата
    new_chat_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_chat_entry, pattern="^new_chat$")],
        states={
            SET_NEW_CHAT_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_chat_title),
            ]
        },
        fallbacks=[],
        map_to_parent={},
    )

    # ConversationHandler: переименование
    rename_chat_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(rename_chat_entry, pattern=r"^rename_\d+$")],
        states={
            SET_RENAME_CHAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rename_chat_finish),
            ]
        },
        fallbacks=[],
        map_to_parent={},
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))

    # Конверсейшены
    application.add_handler(instructions_conv_handler)
    application.add_handler(new_chat_conv_handler)
    application.add_handler(rename_chat_conv_handler)

    # Инлайн-кнопки
    application.add_handler(CallbackQueryHandler(button_handler))

    # Текстовые сообщения
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()

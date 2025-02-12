# handlers/chats.py
import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import (
    MAX_TELEGRAM_TEXT,
    PAGE_SIZE,
    TRUNCATE_SUFFIX
)
from db import (
    get_user_chats,
    get_favorite_chats,
    get_chat_messages,
    get_chat_title_by_id,
    set_chat_favorite,
    get_active_chat_id,
)
from db import delete_chat, rename_chat, set_active_chat_id
from utils import truncate_if_too_long

logger = logging.getLogger(__name__)

# Показ списка всех чатов
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

# Показ избранных чатов
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


# Показ под-меню конкретного чата
async def show_single_chat_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_db_id: int):
    from db import get_chat_title_by_id  # чтобы избежать круговых импортов
    query = update.callback_query
    chat_title = get_chat_title_by_id(chat_db_id)
    if not chat_title:
        await query.edit_message_text("Чат не найден (возможно, удалён).", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="all_chats")]
        ]))
        return

    # Проверяем, избранный ли он
    conn = sqlite3.connect("bot_storage.db")
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

# Показ истории (пагинация)
async def show_chat_history(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_db_id: int, page: int):
    query = update.callback_query
    messages = get_chat_messages(chat_db_id)
    total_messages = len(messages)

    from config import PAGE_SIZE
    start_index = page * PAGE_SIZE
    end_index = start_index + PAGE_SIZE
    page_messages = messages[start_index:end_index]

    if not page_messages:
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
    text_result = truncate_if_too_long(text_result)  # обрезка

    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("◀️", callback_data=f"history_{chat_db_id}:page_{page-1}"))
    if end_index < total_messages:
        buttons.append(InlineKeyboardButton("▶️", callback_data=f"history_{chat_db_id}:page_{page+1}"))

    buttons.append(InlineKeyboardButton("🔙 Назад", callback_data=f"open_chat_{chat_db_id}"))

    reply_markup = InlineKeyboardMarkup([buttons])
    await query.edit_message_text(text_result, reply_markup=reply_markup)

# app/telegram_bot/handlers/chats.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.config import PAGE_SIZE
from app.telegram_bot.utils import truncate_if_too_long

# Предположим, вы создали chat_service с методами:
#   async def get_user_chats(session, user_id: int) -> list[ChatModel]
#   async def get_favorite_chats(session, user_id: int) -> list[ChatModel]
#   async def get_chat_title(session, chat_db_id: int) -> str | None
#   async def is_favorite_chat(session, chat_db_id: int) -> bool
#   async def set_chat_favorite(session, chat_db_id: int, is_favorite: bool)
#   async def delete_chat(session, chat_db_id: int)
#   async def rename_chat(session, chat_db_id: int, new_title: str)
#   async def get_chat_messages(session, chat_db_id: int) -> list[dict]
# и т.д. (подобно старым функциям в db.py).
#
from app.services import chat_service

logger = logging.getLogger(__name__)

async def show_all_chats_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показ списка всех чатов пользователя (inline-кнопки).
    """
    query = update.callback_query
    user_id = query.message.chat.id

    # 1. Получаем session_factory
    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data.")
        await query.edit_message_text("Ошибка: нет подключения к БД.")
        return

    # 2. Загружаем чаты
    async with session_factory() as session:
        all_chats = await chat_service.get_user_chats(session, user_id)

    if not all_chats:
        text = "У вас пока нет ни одного чата."
        keyboard = [
            [
                InlineKeyboardButton("Создать новый чат", callback_data="new_chat"),
                InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu"),
            ],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Формируем текст
    text_lines = ["Ваши чаты:\n"]
    keyboard = []
    for chat_data in all_chats:
        db_id = chat_data.id
        title = chat_data.title
        is_fav = chat_data.is_favorite
        prefix = "⭐ " if is_fav else ""
        text_lines.append(f"• ID {db_id}: {prefix}{title}")
        keyboard.append([
            InlineKeyboardButton(
                f"{prefix}{title}",
                callback_data=f"open_chat_{db_id}"
            )
        ])

    text_result = "\n".join(text_lines)
    keyboard.append([
        InlineKeyboardButton("Создать новый чат", callback_data="new_chat"),
        InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")
    ])

    await query.edit_message_text(text_result, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_favorite_chats_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показ избранных чатов (⭐).
    """
    query = update.callback_query
    user_id = query.message.chat.id

    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data.")
        await query.edit_message_text("Ошибка: нет подключения к БД.")
        return

    async with session_factory() as session:
        fav_chats = await chat_service.get_favorite_chats(session, user_id)

    if not fav_chats:
        text = "У вас нет избранных чатов."
        keyboard = [
            [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text_lines = ["Избранные чаты:\n"]
    keyboard = []
    for chat_data in fav_chats:
        db_id = chat_data.id
        title = chat_data.title
        prefix = "⭐ "
        text_lines.append(f"• ID {db_id}: {prefix}{title}")
        keyboard.append([
            InlineKeyboardButton(f"{prefix}{title}", callback_data=f"open_chat_{db_id}")
        ])

    text_result = "\n".join(text_lines)
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")])

    await query.edit_message_text(text_result, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_single_chat_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_db_id: int):
    """
    Показ подменю конкретного чата: активировать, переименовать, посмотреть историю, избранное, удалить.
    """
    query = update.callback_query

    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data.")
        await query.edit_message_text("Ошибка: нет подключения к БД.")
        return

    async with session_factory() as session:
        chat_title = await chat_service.get_chat_title(session, chat_db_id)
        if not chat_title:
            await query.edit_message_text(
                "Чат не найден (возможно, удалён).",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="all_chats")]
                ])
            )
            return

        is_fav = await chat_service.is_favorite_chat(session, chat_db_id)

    favorite_btn_text = "Убрать из избранного" if is_fav else "Добавить в избранное"
    favorite_cb = f"unfav_{chat_db_id}" if is_fav else f"fav_{chat_db_id}"

    text = f"Чат: {chat_title}\nID: {chat_db_id}\n\nВыберите действие:"
    keyboard = [
        [
            InlineKeyboardButton("Назначить активным", callback_data=f"set_active_{chat_db_id}"),
            InlineKeyboardButton("Переименовать", callback_data=f"rename_{chat_db_id}"),
        ],
        [
            InlineKeyboardButton("История", callback_data=f"history_{chat_db_id}:page_0"),
            InlineKeyboardButton(favorite_btn_text, callback_data=favorite_cb),
        ],
        [InlineKeyboardButton("Удалить", callback_data=f"delete_chat_{chat_db_id}")],
        [InlineKeyboardButton("🔙 Назад к списку", callback_data="all_chats")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_chat_history(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_db_id: int, page: int):
    """
    Показ истории сообщений (с пагинацией).
    """
    query = update.callback_query

    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data.")
        await query.edit_message_text("Ошибка: нет подключения к БД.")
        return

    async with session_factory() as session:
        messages = await chat_service.get_chat_messages(session, chat_db_id)
    total_messages = len(messages)

    start_index = page * PAGE_SIZE
    end_index = start_index + PAGE_SIZE
    page_messages = messages[start_index:end_index]

    # Если нет сообщений на этой странице, откатываемся на предыдущую (если page>0)
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
    text_result = truncate_if_too_long(text_result)

    # Кнопки пагинации
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("◀️", callback_data=f"history_{chat_db_id}:page_{page-1}"))
    if end_index < total_messages:
        buttons.append(InlineKeyboardButton("▶️", callback_data=f"history_{chat_db_id}:page_{page+1}"))

    # Кнопка "Назад" к меню чата
    buttons.append(InlineKeyboardButton("🔙 Назад", callback_data=f"open_chat_{chat_db_id}"))

    reply_markup = InlineKeyboardMarkup([buttons])
    await query.edit_message_text(text_result, reply_markup=reply_markup)

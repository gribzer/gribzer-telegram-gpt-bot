# app/telegram_bot/handlers/chats.py

import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import ContextTypes
from app.config import PAGE_SIZE
from app.telegram_bot.utils import truncate_if_too_long
from app.services import chat_service

logger = logging.getLogger(__name__)

# Пусть у нас одна "обложка" для всех операций с чатами:
CHATS_COVER = "app/telegram_bot/images/Chats.png"


async def show_all_chats_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показ списка всех чатов пользователя (inline-кнопки) + обложка Chats.png.
    """
    query = update.callback_query
    user_id = query.message.chat.id

    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data.")
        # Меняем сообщение на картинку + текст ошибки
        media = InputMediaPhoto(open(CHATS_COVER, "rb"), caption="Ошибка: нет подключения к БД.")
        await query.edit_message_media(media=media)
        return

    # Загружаем чаты
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
        media = InputMediaPhoto(open(CHATS_COVER, "rb"), caption=text)
        await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
        return

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
    # Добавляем кнопки
    keyboard.append([
        InlineKeyboardButton("Создать новый чат", callback_data="new_chat"),
        InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")
    ])
    media = InputMediaPhoto(open(CHATS_COVER, "rb"), caption=text_result)
    await query.edit_message_media(
        media=media,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_favorite_chats_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показ избранных чатов (⭐) + та же обложка (или сделайте свою).
    """
    query = update.callback_query
    user_id = query.message.chat.id

    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data.")
        media = InputMediaPhoto(open(CHATS_COVER, "rb"), caption="Ошибка: нет подключения к БД.")
        await query.edit_message_media(media=media)
        return

    async with session_factory() as session:
        fav_chats = await chat_service.get_favorite_chats(session, user_id)

    if not fav_chats:
        text = "У вас нет избранных чатов."
        keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]]
        media = InputMediaPhoto(open(CHATS_COVER, "rb"), caption=text)
        await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
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
    media = InputMediaPhoto(open(CHATS_COVER, "rb"), caption=text_result)
    await query.edit_message_media(
        media=media,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_single_chat_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_db_id: int):
    """
    Показ подменю конкретного чата: активировать, переименовать, посмотреть историю, избранное, удалить.
    """
    query = update.callback_query

    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data.")
        media = InputMediaPhoto(open(CHATS_COVER, "rb"), caption="Ошибка: нет подключения к БД.")
        await query.edit_message_media(media=media)
        return

    async with session_factory() as session:
        chat_title = await chat_service.get_chat_title(session, chat_db_id)
        if not chat_title:
            media = InputMediaPhoto(open(CHATS_COVER, "rb"), caption="Чат не найден (возможно, удалён).")
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="all_chats")]]
            await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
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
    media = InputMediaPhoto(open(CHATS_COVER, "rb"), caption=text)
    await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_chat_history(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_db_id: int, page: int):
    """
    Показ истории сообщений (с пагинацией) + обложка Chats.png.
    """
    query = update.callback_query

    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data.")
        media = InputMediaPhoto(open(CHATS_COVER, "rb"), caption="Ошибка: нет подключения к БД.")
        await query.edit_message_media(media=media)
        return

    async with session_factory() as session:
        messages = await chat_service.get_chat_messages(session, chat_db_id)

    total_messages = len(messages)
    start_index = page * PAGE_SIZE
    end_index = start_index + PAGE_SIZE
    page_messages = messages[start_index:end_index]

    if not page_messages:
        if page > 0:
            return await show_chat_history(update, context, chat_db_id, page - 1)
        else:
            caption_text = "В этом чате нет сообщений."
            kb = [[InlineKeyboardButton("🔙 Назад", callback_data=f"open_chat_{chat_db_id}")]]
            media = InputMediaPhoto(open(CHATS_COVER, "rb"), caption=caption_text)
            await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(kb))
            return

    text_lines = [f"История чата {chat_db_id}, страница {page + 1}"]
    for i, msg in enumerate(page_messages, start=start_index + 1):
        role_emoji = "👤" if msg["role"] == "user" else "🤖"
        text_lines.append(f"{i}) {role_emoji} {msg['role']}: {msg['content']}")

    text_result = truncate_if_too_long("\n".join(text_lines))

    # Кнопки пагинации
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("◀️", callback_data=f"history_{chat_db_id}:page_{page-1}"))
    if end_index < total_messages:
        buttons.append(InlineKeyboardButton("▶️", callback_data=f"history_{chat_db_id}:page_{page+1}"))

    # Кнопка "Назад" к меню чата
    buttons.append(InlineKeyboardButton("🔙 Назад", callback_data=f"open_chat_{chat_db_id}"))
    reply_markup = InlineKeyboardMarkup([buttons])

    media = InputMediaPhoto(open(CHATS_COVER, "rb"), caption=text_result)
    await query.edit_message_media(media=media, reply_markup=reply_markup)

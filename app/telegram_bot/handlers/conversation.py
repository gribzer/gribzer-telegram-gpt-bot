# app/telegram_bot/handlers/conversation.py

import logging
from telegram import Update, InputMediaPhoto
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from app.config import (
    SET_NEW_CHAT_TITLE,
    SET_RENAME_CHAT,
    # INSTRUCTIONS_INPUT  # см. ниже, если нужно
)
from app.telegram_bot.handlers.menu import menu_command

# Импортируем сервисы
from app.services.chat_service import create_chat, rename_chat
from app.services.user_service import set_active_chat_id, set_user_instructions

logger = logging.getLogger(__name__)

# Обложка (одна на все шаги). Можно сделать разные, если нужно.
CONVERSATION_COVER = "app/telegram_bot/images/Chats.png"

# --------------------------------------------------
#  (B) СОЗДАНИЕ НОВОГО ЧАТА
# --------------------------------------------------
async def new_chat_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начинает диалог по созданию нового чата: просим ввести название.
    Раньше мы делали query.edit_message_text(...), теперь покажем картинку + подпись.
    """
    query = update.callback_query
    await query.answer()

    # Текст запроса
    text = "Введите название нового чата (или /cancel для отмены):"
    media = InputMediaPhoto(open(CONVERSATION_COVER, "rb"), caption=text)

    await query.edit_message_media(media=media)
    return SET_NEW_CHAT_TITLE


async def set_new_chat_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Принимает введённое название и создаёт новый чат в БД.
    Здесь приходит обычное сообщение (update.message).
    """
    user_text = update.message.text.strip()
    if user_text.lower() in ["/cancel", "отмена", "назад"]:
        # Отправим фото, что действие отменено
        cancel_text = "Создание чата отменено."
        with open(CONVERSATION_COVER, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption=cancel_text)
        await menu_command(update, context)
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data. Can't create chat.")
        with open(CONVERSATION_COVER, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption="Ошибка: нет подключения к БД.")
        return ConversationHandler.END

    # Создаём чат
    async with session_factory() as session:
        new_chat_obj = await create_chat(session, user_id=chat_id, title=user_text)
        # Назначаем его активным для пользователя
        await set_active_chat_id(session, chat_id, new_chat_obj.id)

    # Уведомляем, что чат создан
    confirm_text = f"Чат создан и выбран в качестве активного! (ID: {new_chat_obj.id})"
    with open(CONVERSATION_COVER, "rb") as photo:
        await update.message.reply_photo(photo=photo, caption=confirm_text)

    # Возвращаемся в меню
    await menu_command(update, context)
    return ConversationHandler.END


# --------------------------------------------------
#  (C) ПЕРЕИМЕНОВАНИЕ ЧАТА
# --------------------------------------------------
async def rename_chat_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начинает диалог: просим новое название чата.
    """
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_db_id = int(data.split("_")[-1])
    context.user_data["rename_chat_id"] = chat_db_id

    text = "Введите новое название чата (или /cancel для отмены):"
    media = InputMediaPhoto(open(CONVERSATION_COVER, "rb"), caption=text)
    await query.edit_message_media(media=media)

    return SET_RENAME_CHAT


async def rename_chat_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Принимает новое название и переименовывает чат в БД.
    """
    user_text = update.message.text.strip()
    if user_text.lower() in ["/cancel", "отмена", "назад"]:
        cancel_text = "Переименование отменено."
        with open(CONVERSATION_COVER, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption=cancel_text)
        await menu_command(update, context)
        return ConversationHandler.END

    chat_db_id = context.user_data.get("rename_chat_id")
    if not chat_db_id:
        # Не знаем, что переименовывать
        with open(CONVERSATION_COVER, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption="Не удалось найти чат для переименования.")
        await menu_command(update, context)
        return ConversationHandler.END

    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found. Can't rename chat.")
        with open(CONVERSATION_COVER, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption="Ошибка: нет подключения к БД.")
        return ConversationHandler.END

    async with session_factory() as session:
        await rename_chat(session, chat_db_id, user_text)

    result_text = f"Чат {chat_db_id} переименован!"
    with open(CONVERSATION_COVER, "rb") as photo:
        await update.message.reply_photo(photo=photo, caption=result_text)

    await menu_command(update, context)
    return ConversationHandler.END


# --------------------------------------------------
#  (D) «МЕНЮ ИНСТРУКЦИЙ»: ДОБАВИТЬ / РЕДАКТИРОВАТЬ
# --------------------------------------------------
INSTRUCTIONS_INPUT = 900

async def instructions_add_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начинает Conversation для ДОБАВЛЕНИЯ инструкций.
    """
    query = update.callback_query
    await query.answer()

    text = "Введите текст инструкций (или /cancel для отмены):"
    media = InputMediaPhoto(open(CONVERSATION_COVER, "rb"), caption=text)
    await query.edit_message_media(media=media)

    context.user_data["instructions_mode"] = "add"
    return INSTRUCTIONS_INPUT


async def instructions_edit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начинает Conversation для РЕДАКТИРОВАНИЯ инструкций.
    """
    query = update.callback_query
    await query.answer()

    text = "Введите новые инструкции (или /cancel для отмены):"
    media = InputMediaPhoto(open(CONVERSATION_COVER, "rb"), caption=text)
    await query.edit_message_media(media=media)

    context.user_data["instructions_mode"] = "edit"
    return INSTRUCTIONS_INPUT


async def instructions_input_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Принимает введённые инструкции и сохраняет их в БД.
    """
    user_text = update.message.text.strip()
    if user_text.lower() in ["/cancel", "отмена", "назад"]:
        with open(CONVERSATION_COVER, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption="Операция с инструкциями отменена.")
        await menu_command(update, context)
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found. Can't set instructions.")
        with open(CONVERSATION_COVER, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption="Ошибка: нет подключения к БД.")
        return ConversationHandler.END

    async with session_factory() as session:
        await set_user_instructions(session, chat_id, user_text)

    # Инструкции сохранены
    with open(CONVERSATION_COVER, "rb") as photo:
        await update.message.reply_photo(photo=photo, caption="Инструкции успешно сохранены!")

    await menu_command(update, context)
    return ConversationHandler.END

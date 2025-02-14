# app/telegram_bot/handlers/conversation.py

import logging
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from app.config import (
    SET_NEW_CHAT_TITLE,
    SET_RENAME_CHAT
)
from app.telegram_bot.handlers.menu import menu_command

# Импортируем сервисы
from app.services.chat_service import create_chat, rename_chat
from app.services.user_service import set_active_chat_id, set_user_instructions

logger = logging.getLogger(__name__)

# --------------------------------------------------
#  (B) СОЗДАНИЕ НОВОГО ЧАТА
# --------------------------------------------------
async def new_chat_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начинает диалог по созданию нового чата: просим ввести название.
    """
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите название нового чата (или /cancel для отмены):")

    return SET_NEW_CHAT_TITLE

async def set_new_chat_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Принимает введённое название и создаёт новый чат в БД.
    """
    user_text = update.message.text.strip()
    if user_text.lower() in ["/cancel", "отмена", "назад"]:
        await update.message.reply_text("Создание чата отменено.")
        await menu_command(update, context)
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data. Can't create chat.")
        await update.message.reply_text("Ошибка: нет подключения к БД.")
        return ConversationHandler.END

    async with session_factory() as session:
        # Создаём чат
        new_chat_obj = await create_chat(session, user_id=chat_id, title=user_text)
        # Назначаем его активным для пользователя
        await set_active_chat_id(session, chat_id, new_chat_obj.id)

    await update.message.reply_text(f"Чат создан и выбран в качестве активного! (ID: {new_chat_obj.id})")
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

    await query.edit_message_text("Введите новое название чата (или /cancel для отмены):")
    return SET_RENAME_CHAT

async def rename_chat_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Принимает новое название и переименовывает чат в БД.
    """
    user_text = update.message.text.strip()
    if user_text.lower() in ["/cancel", "отмена", "назад"]:
        await update.message.reply_text("Переименование отменено.")
        await menu_command(update, context)
        return ConversationHandler.END

    chat_db_id = context.user_data.get("rename_chat_id")
    if not chat_db_id:
        await update.message.reply_text("Не удалось найти чат для переименования.")
        await menu_command(update, context)
        return ConversationHandler.END

    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found. Can't rename chat.")
        await update.message.reply_text("Ошибка: нет подключения к БД.")
        return ConversationHandler.END

    async with session_factory() as session:
        await rename_chat(session, chat_db_id, user_text)

    await update.message.reply_text(f"Чат {chat_db_id} переименован!")
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
    await query.edit_message_text("Введите текст инструкций (или /cancel для отмены):")

    context.user_data["instructions_mode"] = "add"
    return INSTRUCTIONS_INPUT

async def instructions_edit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начинает Conversation для РЕДАКТИРОВАНИЯ инструкций.
    """
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите новые инструкции (или /cancel для отмены):")

    context.user_data["instructions_mode"] = "edit"
    return INSTRUCTIONS_INPUT

async def instructions_input_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Принимает введённые инструкции и сохраняет их в БД.
    """
    user_text = update.message.text.strip()
    if user_text.lower() in ["/cancel", "отмена", "назад"]:
        await update.message.reply_text("Операция с инструкциями отменена.")
        await menu_command(update, context)
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data. Can't set instructions.")
        await update.message.reply_text("Ошибка: нет подключения к БД.")
        return ConversationHandler.END

    async with session_factory() as session:
        await set_user_instructions(session, chat_id, user_text)

    await update.message.reply_text("Инструкции успешно сохранены!")
    await menu_command(update, context)
    return ConversationHandler.END

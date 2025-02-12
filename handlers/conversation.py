# handlers/conversation.py
import logging
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from config import (
    SET_INSTRUCTIONS,
    SET_NEW_CHAT_TITLE,
    SET_RENAME_CHAT
)
from db import (
    set_user_instructions,
    create_new_chat,
    set_active_chat_id,
    rename_chat
)
from handlers.menu import menu_command

logger = logging.getLogger(__name__)

# --------------------------------------------------
#  (A) СТАРЫЙ вариант "Инструкции" — сразу ввод
# --------------------------------------------------
async def update_instructions_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Если пользователь нажимает "Инструкции" по старой логике,
    сразу просим ввести текст.
    """
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Пожалуйста, отправьте новые инструкции (или /cancel для отмены):")
    return SET_INSTRUCTIONS

async def receive_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if user_text.lower() in ["меню", "назад", "отмена", "/cancel"]:
        await update.message.reply_text("Обновление инструкций отменено.")
        await menu_command(update, context)
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    set_user_instructions(chat_id, user_text)

    await update.message.reply_text("Инструкции обновлены!")
    await menu_command(update, context)
    return ConversationHandler.END


# --------------------------------------------------
#  (B) СОЗДАНИЕ НОВОГО ЧАТА
# --------------------------------------------------
async def new_chat_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите название нового чата (или /cancel для отмены):")

    return SET_NEW_CHAT_TITLE

async def set_new_chat_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if user_text.lower() in ["/cancel", "отмена", "назад"]:
        await update.message.reply_text("Создание чата отменено.")
        await menu_command(update, context)
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    new_chat_id = create_new_chat(chat_id, user_text)
    set_active_chat_id(chat_id, new_chat_id)

    await update.message.reply_text(f"Чат создан и выбран в качестве активного! (ID: {new_chat_id})")
    await menu_command(update, context)
    return ConversationHandler.END

# --------------------------------------------------
#  (C) ПЕРЕИМЕНОВАНИЕ ЧАТА
# --------------------------------------------------
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
    if user_text.lower() in ["/cancel", "отмена", "назад"]:
        await update.message.reply_text("Переименование отменено.")
        await menu_command(update, context)
        return ConversationHandler.END

    chat_db_id = context.user_data.get("rename_chat_id")
    if not chat_db_id:
        await update.message.reply_text("Не удалось найти чат для переименования.")
        await menu_command(update, context)
        return ConversationHandler.END

    rename_chat(chat_db_id, user_text)
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
    # Сохраняем (логика add/edit одинакова)
    set_user_instructions(chat_id, user_text)

    await update.message.reply_text("Инструкции успешно сохранены!")
    await menu_command(update, context)
    return ConversationHandler.END

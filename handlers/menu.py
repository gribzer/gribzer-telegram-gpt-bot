# handlers/menu.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from db import (
    get_active_chat_id,
    get_user_model,
    get_user_chats,
    get_chat_title_by_id
)
from config import (
    DEFAULT_INSTRUCTIONS,
    AVAILABLE_MODELS
)


logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Меню"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    welcome_text = (
        "Привет! Я бот, использующий Proxy API для ChatGPT.\n"
        "Нажмите кнопку «Меню», чтобы увидеть настройки и инструкции."
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Генерируем текст с инфой о текущем чате, модели и количестве чатов
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

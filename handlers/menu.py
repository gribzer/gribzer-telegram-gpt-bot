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

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start - Приветственное сообщение. 
    Здесь можно при желании отправить ReplyKeyboard, 
    но мы теперь используем встроенное Telegram-меню (через setMyCommands).
    """
    text = (
        "Привет! Я бот, использующий Proxy API для ChatGPT.\n"
        "Нажмите /menu, чтобы увидеть настройки и инструкции.\n"
        "Либо откройте меню бота (синяя кнопка слева от ввода текста)."
    )
    await update.message.reply_text(text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /help - Команда для быстрого вызова справки.
    """
    text = (
        "❓ Помощь по боту:\n"
        "1. Отправьте любое текстовое сообщение – бот ответит.\n"
        "2. /menu – главное меню с чатом, моделями и инструкциями.\n"
        "3. /help – эта справка.\n"
        "4. Используйте кнопку меню слева от поля ввода, если поддерживается."
    )
    await update.message.reply_text(text)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /menu – показывает главное меню (inline-кнопки).
    """
    # Генерируем текст с инфой о текущем чате, модели и количестве чатов
    chat_id = (update.message.chat.id if update.message 
               else update.callback_query.message.chat.id)
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
        f"Всего чатов: {total_chats}\n\n"
        "Выберите опцию:"
    )

    # Формируем инлайн-клавиатуру (по 2 кнопки в ряд)
    keyboard = [
        [
            InlineKeyboardButton("📑 Все чаты", callback_data="all_chats"),
            InlineKeyboardButton("⭐ Избранные чаты", callback_data="favorite_chats"),
        ],
        [
            InlineKeyboardButton("🤖 Сменить модель", callback_data="change_model"),
            InlineKeyboardButton("📝 Инструкции", callback_data="update_instructions"),
        ],
        [
            InlineKeyboardButton("❓ Помощь", callback_data="help"),
            InlineKeyboardButton("💬 История", callback_data="history_current_chat"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(main_text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(main_text, reply_markup=reply_markup)

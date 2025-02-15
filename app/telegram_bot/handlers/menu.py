# app/telegram_bot/handlers/menu.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.services.user_service import get_active_chat_id, get_user_model
from app.services.chat_service import get_user_chats, get_chat_title

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start - Приветственное сообщение.
    Можно отправить краткую инструкцию или меню.
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
        "2. /menu – главное меню с чатами, моделями и инструкциями.\n"
        "3. /help – эта справка.\n"
        "4. /cabinet – личный кабинет (баланс и платежи).\n"
        "5. Используйте кнопку меню слева от поля ввода, если поддерживается."
    )
    await update.message.reply_text(text)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /menu – показывает главное меню (inline-кнопки).
    """
    # Определяем, откуда пришёл Update (Message или CallbackQuery)
    if update.message:
        chat_id = update.message.chat.id
    else:
        chat_id = update.callback_query.message.chat.id

    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data.")
        main_text = (
            "Ошибка: Нет подключения к БД.\n\n"
            "Выберите опцию:"
        )
        keyboard = [
            [InlineKeyboardButton("❓ Помощь", callback_data="help")],
            [InlineKeyboardButton("🏦 Личный кабинет", callback_data="show_cabinet")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Редактируем или отправляем новое сообщение
        if update.message:
            await update.message.reply_text(main_text, reply_markup=reply_markup)
        else:
            await update.callback_query.edit_message_text(main_text, reply_markup=reply_markup)
        return

    # Запрашиваем данные из сервиса
    async with session_factory() as session:
        active_id = await get_active_chat_id(session, chat_id)
        model_name = await get_user_model(session, chat_id) or "—"
        user_chats = await get_user_chats(session, chat_id)
        total_chats = len(user_chats)

        if active_id:
            active_title = await get_chat_title(session, active_id) or f"(ID {active_id})"
        else:
            active_title = "не выбран"

    # Формируем текст меню
    main_text = (
        f"Текущий чат: {active_title}\n"
        f"Модель: {model_name}\n"
        f"Всего чатов: {total_chats}\n\n"
        "Выберите опцию:"
    )

    # Формируем инлайн-клавиатуру (пример: по 2 кнопки в ряд)
    keyboard = [
        [
            InlineKeyboardButton("📑 Все чаты", callback_data="all_chats"),
            InlineKeyboardButton("⭐ Избранное", callback_data="favorite_chats"),
        ],
        [
            InlineKeyboardButton("🤖 Сменить модель", callback_data="change_model"),
            InlineKeyboardButton("💬 История чата", callback_data="history_current_chat"),
        ],
        [
            InlineKeyboardButton("📝 Инструкции", callback_data="update_instructions"),
            InlineKeyboardButton("🏦 Личный кабинет", callback_data="show_cabinet"),
        ],
        [
            InlineKeyboardButton("❓ Помощь", callback_data="help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем/редактируем сообщение
    if update.message:
        await update.message.reply_text(main_text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(main_text, reply_markup=reply_markup)

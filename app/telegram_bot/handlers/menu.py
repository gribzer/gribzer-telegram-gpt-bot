# app/telegram_bot/handlers/menu.py

import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import ContextTypes

from app.services.user_service import get_active_chat_id, get_user_model
from app.services.chat_service import get_user_chats, get_chat_title

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start - Приветственное сообщение с обложкой Start_cover.png
    """
    cover_path = "app/telegram_bot/images/Start_cover.png"
    text = (
        "Привет! Я бот, использующий Proxy API для ChatGPT.\n"
        "Нажмите /menu, чтобы увидеть настройки и инструкции.\n"
        "Либо откройте меню бота (синяя кнопка слева от ввода текста)."
    )

    # Если это новое сообщение (пользователь набрал /start)
    if update.message:
        with open(cover_path, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=text
            )
    else:
        # Если это callback_query (редко для /start)
        query = update.callback_query
        await query.answer()
        media = InputMediaPhoto(open(cover_path, "rb"), caption=text)
        await query.edit_message_media(media=media)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /help - Высылаем Help.png и текст справки.
    """
    cover_path = "app/telegram_bot/images/Help.png"
    text = (
        "❓ Помощь по боту:\n"
        "1. Отправьте любое текстовое сообщение – бот ответит.\n"
        "2. /menu – главное меню с чатами, моделями и инструкциями.\n"
        "3. /help – эта справка.\n"
        "4. /cabinet – личный кабинет.\n"
        "5. Используйте кнопку меню слева от поля ввода."
    )

    if update.message:
        with open(cover_path, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption=text)
    else:
        query = update.callback_query
        await query.answer()
        media = InputMediaPhoto(open(cover_path, "rb"), caption=text)
        await query.edit_message_media(media=media)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /menu – Главное меню (Menu.png + текст + инлайн-кнопки).
    При колбэке редактируем то же сообщение через edit_message_media.
    """
    cover_path = "app/telegram_bot/images/Menu.png"

    # Определяем chat_id
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
    else:
        # Запрашиваем из БД нужные данные
        async with session_factory() as session:
            active_id = await get_active_chat_id(session, chat_id)
            model_name = await get_user_model(session, chat_id) or "—"
            user_chats = await get_user_chats(session, chat_id)
            total_chats = len(user_chats)

            if active_id:
                active_title = await get_chat_title(session, active_id) or f"(ID {active_id})"
            else:
                active_title = "не выбран"

        main_text = (
            f"Текущий чат: {active_title}\n"
            f"Модель: {model_name}\n"
            f"Всего чатов: {total_chats}\n\n"
            "Выберите опцию:"
        )
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

    # Текст для подписии (caption)
    caption_text = main_text

    if update.message:
        # Новое сообщение (/menu)
        with open(cover_path, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=caption_text,
                reply_markup=reply_markup
            )
    else:
        # Колбэк: редактируем фото + подпись
        query = update.callback_query
        await query.answer()
        media = InputMediaPhoto(open(cover_path, "rb"), caption=caption_text)
        await query.edit_message_media(
            media=media,
            reply_markup=reply_markup
        )

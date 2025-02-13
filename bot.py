#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import openai
import logging
import os
import json

from telegram import Update, Bot
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler,
    CallbackQueryHandler
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Установите уровень логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузите токен Telegram бота и API-ключ OpenAI из переменных среды
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

# Константы для ConversationHandler
STATE_START = 0
STATE_CHAT = 1

def start(update: Update, context: CallbackContext):
    """Команда /start – приветственное сообщение и начало взаимодействия."""
    update.message.reply_text(
        "Привет! Я GPT-бот. Задавай вопросы или используй /help для справки."
    )
    return STATE_CHAT

def help_command(update: Update, context: CallbackContext):
    """Команда /help – выводит подсказку по доступным командам."""
    help_text = (
        "Список доступных команд:\n"
        "/start - начать работу с ботом\n"
        "/help - показать это сообщение\n"
        "/instructions - получить инструкции\n"
        "Просто напишите мне сообщение, и я постараюсь ответить!\n"
    )
    update.message.reply_text(help_text)

def instructions(update: Update, context: CallbackContext):
    """
    Команда /instructions – здесь вы можете разместить короткую инструкцию
    по использованию бота или дополнительные сведения.
    """
    instruction_text = (
        "Инструкции по работе с ботом:\n"
        "1. Начните диалог командой /start.\n"
        "2. Задавайте вопросы или вводите запросы, и я отвечу.\n"
        "3. Для повторной подсказки используйте /help.\n"
        "4. Используйте /instructions, чтобы снова увидеть эту инструкцию.\n"
    )
    update.message.reply_text(instruction_text)

def cancel(update: Update, context: CallbackContext):
    """Команда /cancel – завершает текущий диалог (ConversationHandler)."""
    update.message.reply_text("Диалог завершён. Наберите /start, чтобы начать заново.")
    return ConversationHandler.END

def chat_handler(update: Update, context: CallbackContext):
    """Основная логика ответа бота: отправляет запрос в OpenAI и возвращает ответ."""
    user_text = update.message.text

    # Пример базового обращения к OpenAI GPT-3.5 Turbo
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": user_text}],
            max_tokens=150,
            n=1,
            stop=None,
            temperature=0.7,
        )
        # Извлекаем ответ
        bot_reply = response['choices'][0]['message']['content']
        update.message.reply_text(bot_reply)
    except Exception as e:
        logger.error(f"Ошибка при обращении к OpenAI: {e}")
        update.message.reply_text("Произошла ошибка при получении ответа. Попробуйте позже.")

    return STATE_CHAT

def main():
    """Основная точка входа в программу: настраивает бота и запускает polling."""
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Устанавливаем ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start),
                      CommandHandler("instructions", instructions)],
        states={
            STATE_CHAT: [
                MessageHandler(Filters.text & ~Filters.command, chat_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Регистрируем обработчики команд
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(conv_handler)

    # Запускаем бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

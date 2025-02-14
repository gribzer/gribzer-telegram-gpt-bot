import logging
import httpx
from telegram import Update
from telegram.ext import ContextTypes

from db import (
    get_user_model,
    set_user_model,
    get_active_chat_id,
    create_new_chat,
    set_active_chat_id,
    get_chat_messages,
    get_user_instructions,
    add_message_to_chat
)
from config import (
    TIMEOUT,             # TIMEOUT задаётся в config.py
    DEFAULT_INSTRUCTIONS,
    PROXY_API_KEY        # <-- ВАЖНО: Импортируем сам ключ отсюда
)
from utils import convert_to_telegram_markdown_v2
from telegram.error import BadRequest

logger = logging.getLogger(__name__)

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    # Пример вызова команды "меню"
    if user_text.lower() == "меню":
        from handlers.menu import menu_command
        await menu_command(update, context)
        return

    chat_id = update.effective_chat.id

    # Узнаём текущую модель для пользователя (если нет - ставим по умолчанию)
    selected_model = get_user_model(chat_id)
    if selected_model is None:
        selected_model = "gpt-3.5-turbo"
        set_user_model(chat_id, selected_model)

    # Проверяем, есть ли у пользователя активный "чат" в БД
    active_chat_db_id = get_active_chat_id(chat_id)
    if not active_chat_db_id:
        active_chat_db_id = create_new_chat(chat_id, "Новый чат")
        set_active_chat_id(chat_id, active_chat_db_id)

    # Получаем историю чата и инструкции
    chat_messages = get_chat_messages(active_chat_db_id)
    user_instructions = get_user_instructions(chat_id) or DEFAULT_INSTRUCTIONS

    # Формируем список сообщений для Proxy API
    messages_for_api = []
    if user_instructions.strip():
        messages_for_api.append({"role": "system", "content": user_instructions})
    for msg in chat_messages:
        messages_for_api.append({"role": msg["role"], "content": msg["content"]})
    messages_for_api.append({"role": "user", "content": user_text})

    # Сохраняем сообщение пользователя в базе
    add_message_to_chat(active_chat_db_id, "user", user_text)

    # Запрос к Proxy API
    try:
        url = "https://api.proxyapi.ru/openai/v1/chat/completions"

        # Собираем заголовки
        headers = {
            "Content-Type": "application/json"
        }
        # Берём ключ из config.PROXY_API_KEY (чтобы не зависеть от context.bot_data)
        proxy_api_key = PROXY_API_KEY.strip()
        if proxy_api_key:
            headers["Authorization"] = f"Bearer {proxy_api_key}"

        payload = {
            "model": selected_model,
            "messages": messages_for_api,
            "max_tokens": 500,
            "temperature": 0.2,
            "top_p": 1.0,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            # Извлекаем ответ ассистента
            answer = data["choices"][0]["message"]["content"]

    except httpx.ReadTimeout:
        logger.error("Время ожидания ответа от Proxy API истекло.", exc_info=True)
        answer = "Время ожидания ответа истекло, пожалуйста, повторите запрос позже."
    except Exception as e:
        logger.error(f"Ошибка при вызове Proxy API: {e}", exc_info=True)
        answer = "Произошла ошибка при обработке запроса."

    # Сохраняем ответ ассистента в базе
    add_message_to_chat(active_chat_db_id, "assistant", answer)

    # Форматируем ответ для Telegram (MarkdownV2)
    formatted_answer = convert_to_telegram_markdown_v2(answer)
    try:
        await update.message.reply_text(
            formatted_answer,
            parse_mode="MarkdownV2"
        )
    except BadRequest:
        logger.error("Ошибка при отправке с MarkdownV2, отправляем без форматирования", exc_info=True)
        await update.message.reply_text(answer)

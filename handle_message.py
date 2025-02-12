# handle_message.py
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
    TIMEOUT_CONFIG,
    DEFAULT_INSTRUCTIONS
)
from utils import convert_to_telegram_markdown_v2
from telegram.error import BadRequest

logger = logging.getLogger(__name__)

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    if user_text.lower() == "меню":
        from handlers.menu import menu_command
        await menu_command(update, context)
        return

    chat_id = update.effective_chat.id
    selected_model = get_user_model(chat_id)
    if selected_model is None:
        selected_model = "gpt-3.5-turbo"
        set_user_model(chat_id, selected_model)

    active_chat_db_id = get_active_chat_id(chat_id)
    if not active_chat_db_id:
        active_chat_db_id = create_new_chat(chat_id, "Новый чат")
        set_active_chat_id(chat_id, active_chat_db_id)

    chat_messages = get_chat_messages(active_chat_db_id)
    user_instructions = get_user_instructions(chat_id) or DEFAULT_INSTRUCTIONS

    messages_for_api = []
    if user_instructions.strip():
        messages_for_api.append({"role": "system", "content": user_instructions})
    for msg in chat_messages:
        messages_for_api.append({"role": msg["role"], "content": msg["content"]})
    messages_for_api.append({"role": "user", "content": user_text})

    add_message_to_chat(active_chat_db_id, "user", user_text)

    # Запрос к Proxy API
    try:
        url = "https://api.proxyapi.ru/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {context.bot_data.get('PROXY_API_KEY', '')}",
            "Content-Type": "application/json"
        }
        # или TELEGRAM_TOKEN / PROXY_API_KEY возьмите из config.py
        # headers["Authorization"] = f"Bearer {PROXY_API_KEY}"

        payload = {
            "model": selected_model,
            "messages": messages_for_api,
            "max_tokens": 500,
            "temperature": 0.2,
            "top_p": 1.0,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }

        async with httpx.AsyncClient(**TIMEOUT_CONFIG) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            answer = data["choices"][0]["message"]["content"]
    except httpx.ReadTimeout:
        logger.error("Время ожидания ответа от Proxy API истекло.", exc_info=True)
        answer = "Время ожидания ответа истекло, пожалуйста, повторите запрос позже."
    except Exception as e:
        logger.error(f"Ошибка при вызове Proxy API: {e}", exc_info=True)
        answer = "Произошла ошибка при обработке запроса."

    # Сохраняем ответ
    add_message_to_chat(active_chat_db_id, "assistant", answer)

    formatted_answer = convert_to_telegram_markdown_v2(answer)
    try:
        await update.message.reply_text(
            formatted_answer,
            parse_mode="MarkdownV2"
        )
    except BadRequest:
        logger.error("Ошибка при отправке с MarkdownV2, отправляем без форматирования", exc_info=True)
        await update.message.reply_text(answer)

# app/telegram_bot/handlers/message_handler.py

import logging
import httpx
from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from app.services.subscription_service import (
    can_use_free_request,
    increment_free_requests,
    has_active_subscription
)
from app.services.user_service import (
    get_or_create_user,
    get_active_chat_id,
    set_active_chat_id,
    get_user_model,
    set_user_model,
)
from app.services.chat_service import (
    create_chat,
    add_message,
    get_chat_messages,
)
from app.telegram_bot.proxyapi_client import create_chat_completion
from app.config import (
    TIMEOUT,
    DEFAULT_INSTRUCTIONS,
    PROXY_API_KEY
)
from app.telegram_bot.utils import convert_to_telegram_markdown_v2

logger = logging.getLogger(__name__)

# Обложка для ответов бота (можно заменить на свой путь/имя файла)
MESSAGE_COVER_PATH = "app/telegram_bot/images/Cabinet.png"

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Асинхронный хендлер на входящее текстовое сообщение.
    """
    user_text = update.message.text.strip()

    # Пример вызова "меню":
    if user_text.lower() == "меню":
        from app.telegram_bot.handlers.menu import menu_command
        await menu_command(update, context)
        return

    chat_id = update.effective_chat.id
    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data.")
        await update.message.reply_text("Ошибка: нет подключения к БД.")
        return

    async with session_factory() as session:
        # 1. Получаем/создаём User
        user = await get_or_create_user(session, chat_id)
        balance = user.balance_tokens or 0

        # 2. Проверка баланса / подписки / бесплатных лимитов
        if balance <= 0:
            # Нет токенов, проверим подписку
            if await has_active_subscription(user):
                # У пользователя активная подписка - можно отвечать
                pass
            else:
                # Проверяем бесплатный лимит
                if not await can_use_free_request(session, user):
                    await update.message.reply_text(
                        "Ваш бесплатный лимит исчерпан. Пополните баланс через /cabinet."
                    )
                    return
                else:
                    await increment_free_requests(session, user)
        else:
            # У пользователя > 0 токенов, списываем 1 токен (пример)
            cost = 1
            user.balance_tokens = max(0, balance - cost)
            await session.commit()

        # 3. Узнаём / устанавливаем модель
        selected_model = user.selected_model or "gpt-3.5-turbo"

        # 4. Активный чат
        active_chat_db_id = user.active_chat_id
        if not active_chat_db_id:
            # Создаём новый
            new_chat_obj = await create_chat(session, user_id=chat_id, title="Новый чат")
            user.active_chat_id = new_chat_obj.id
            await session.commit()
            active_chat_db_id = new_chat_obj.id

        # 5. Получаем историю чата + инструкции
        chat_messages_db = await get_chat_messages(session, active_chat_db_id)
        user_instructions = user.instructions or DEFAULT_INSTRUCTIONS

        # Формируем список для API
        messages_for_api = []
        if user_instructions.strip():
            messages_for_api.append({"role": "system", "content": user_instructions})
        for msg in chat_messages_db:
            messages_for_api.append({"role": msg["role"], "content": msg["content"]})
        messages_for_api.append({"role": "user", "content": user_text})

        # Сохраняем сообщение пользователя
        await add_message(session, active_chat_db_id, "user", user_text)

    # 6. Запрос к Proxy API (create_chat_completion)
    try:
        response_data = create_chat_completion(
            model=selected_model,
            messages=messages_for_api,
            temperature=0.2,
            max_tokens=500,
            top_p=1.0,
            frequency_penalty=0,
            presence_penalty=0,
        )
        answer = response_data["choices"][0]["message"]["content"]
    except httpx.ReadTimeout:
        logger.error("Время ожидания ответа от Proxy API истекло.", exc_info=True)
        answer = "Время ожидания ответа истекло, пожалуйста, повторите запрос позже."
    except Exception as e:
        logger.error(f"Ошибка при вызове Proxy API: {e}", exc_info=True)
        answer = "Произошла ошибка при обработке запроса."

    # 7. Сохраняем ответ ассистента
    async with session_factory() as session:
        await add_message(session, active_chat_db_id, "assistant", answer)

    # 8. Отправляем ответ пользователю (картинка + подпись)
    formatted_answer = convert_to_telegram_markdown_v2(answer)

    # Пытаемся отправить в MarkdownV2
    try:
        with open(MESSAGE_COVER_PATH, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=formatted_answer,
                parse_mode="MarkdownV2"
            )
    except BadRequest:
        # Если ошибка при парсинге, отправим без форматирования
        logger.error("Ошибка при отправке MarkdownV2, отправляем без форматирования", exc_info=True)
        with open(MESSAGE_COVER_PATH, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=answer
            )

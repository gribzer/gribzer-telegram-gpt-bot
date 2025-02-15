# app/telegram_bot/handlers/cabinet.py

import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import ContextTypes

from app.services.payment_service import (
    get_user_transactions,
    create_transaction,
    calculate_tokens_for_amount
)
from app.services.tkassa_service import TKassaClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import User

logger = logging.getLogger(__name__)

async def show_cabinet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает личный кабинет с обложкой Cabinet.png
    """
    cover_path = "app/telegram_bot/images/Cabinet.png"

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        chat_id = query.message.chat.id
    else:
        chat_id = update.effective_chat.id

    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data.")
        return

    # Получаем/создаём пользователя, смотрим баланс
    async with session_factory() as session:
        user = await _get_or_create_user(session, chat_id)
        balance = user.balance_tokens or 0
        subscription_active = user.subscription_status  # bool
        sub_text = "Активна" if subscription_active else "Нет"

    text = (
        f"Личный кабинет\n\n"
        f"UID: `{chat_id}`\n"
        f"Баланс: {balance} токенов\n"
        f"Подписка: {sub_text}\n"
    )

    keyboard = [
        [InlineKeyboardButton("Пополнить баланс", callback_data="cabinet_topup")],
        [InlineKeyboardButton("История платежей", callback_data="cabinet_history")],
        [InlineKeyboardButton("Назад в меню", callback_data="back_to_menu")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    caption_text = text  # Пойдёт в caption

    if update.callback_query:
        media = InputMediaPhoto(open(cover_path, "rb"), caption=caption_text, parse_mode="Markdown")
        await update.callback_query.edit_message_media(
            media=media,
            reply_markup=markup
        )
    else:
        with open(cover_path, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=caption_text,
                reply_markup=markup,
                parse_mode="Markdown"
            )


async def cabinet_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Общий callback-хендлер для inline-кнопок в личном кабинете.
    """
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id

    # Для всех колбэков будем по умолчанию оставлять ту же «Cabinet.png»,
    # но с разным caption. Если хотите разные картинки, меняйте cover_path.

    cover_path = "app/telegram_bot/images/Cabinet.png"

    if data == "cabinet_topup":
        text = "Выберите способ пополнения:"
        keyboard = [
            [
                InlineKeyboardButton("Оплатить через T-Кассу", callback_data="cabinet_pay_tkassa"),
                InlineKeyboardButton("Оплатить через Telegram", callback_data="cabinet_pay_telegram")
            ],
            [InlineKeyboardButton("Назад", callback_data="show_cabinet")]
        ]
        markup = InlineKeyboardMarkup(keyboard)

        from telegram import InputMediaPhoto
        media = InputMediaPhoto(open(cover_path, "rb"), caption=text)
        await query.edit_message_media(
            media=media,
            reply_markup=markup
        )
        return

    elif data == "cabinet_history":
        session_factory = context.application.bot_data.get("session_factory")
        if not session_factory:
            logger.error("No session_factory found in bot_data.")
            await query.edit_message_text("Ошибка: не можем получить историю (нет подключения к БД).")
            return

        async with session_factory() as session:
            txns = await get_user_transactions(session, chat_id, limit=5)

        if not txns:
            text = "История платежей пуста."
        else:
            lines = ["Последние транзакции:"]
            for t in txns:
                lines.append(f"• ID {t.id} | {t.amount_rub}₽ => {t.tokens} токенов [{t.status}]")
            text = "\n".join(lines)

        keyboard = [[InlineKeyboardButton("Назад", callback_data="show_cabinet")]]
        markup = InlineKeyboardMarkup(keyboard)
        media = InputMediaPhoto(open(cover_path, "rb"), caption=text)
        await query.edit_message_media(
            media=media,
            reply_markup=markup
        )
        return

    elif data == "cabinet_pay_tkassa":
        # Пример логики для T-Кассы
        amount_rub = 100
        tokens = calculate_tokens_for_amount(amount_rub)

        session_factory = context.application.bot_data.get("session_factory")
        if not session_factory:
            logger.error("No session_factory found in bot_data.")
            await query.edit_message_text("Ошибка: нет соединения с БД.")
            return

        async with session_factory() as session:
            txn = await create_transaction(session, user_id=chat_id, amount_rub=amount_rub, tokens=tokens, method="T-Kassa")
            txn_id = txn.id

        tk_client = TKassaClient()
        amount_coins = int(amount_rub * 100)
        order_id = f"order-{txn_id}"
        description = f"Пополнение баланса, транзакция #{txn_id}"

        try:
            init_resp = await tk_client.init_payment(
                amount_coins,
                order_id,
                description,
                customer_key=str(chat_id)
            )
            success = init_resp.get("Success", False)
            if not success:
                message = init_resp.get("Message", "Ошибка при инициализации платежа")
                text = f"Не удалось создать платёж: {message}"
                keyboard = [[InlineKeyboardButton("Назад", callback_data="show_cabinet")]]
                markup = InlineKeyboardMarkup(keyboard)
                media = InputMediaPhoto(open(cover_path, "rb"), caption=text)
                await query.edit_message_media(media=media, reply_markup=markup)
                return

            payment_url = init_resp.get("PaymentURL")
            text = (
                f"Счёт на {amount_rub}₽ создан!\n"
                f"Транзакция #{txn_id}\n\n"
                f"[Оплатить >>>]({payment_url})"
            )
            keyboard = [[InlineKeyboardButton("Назад", callback_data="show_cabinet")]]
            markup = InlineKeyboardMarkup(keyboard)
            media = InputMediaPhoto(open(cover_path, "rb"), caption=text, parse_mode="Markdown")
            await query.edit_message_media(media=media, reply_markup=markup)

        except Exception as e:
            logger.error(f"Ошибка при init_payment в T-Кассу: {e}", exc_info=True)
            text = "Ошибка при создании платежа. Попробуйте позже."
            keyboard = [[InlineKeyboardButton("Назад", callback_data="show_cabinet")]]
            markup = InlineKeyboardMarkup(keyboard)
            media = InputMediaPhoto(open(cover_path, "rb"), caption=text)
            await query.edit_message_media(media=media, reply_markup=markup)
        return

    elif data == "cabinet_pay_telegram":
        # Запуск Telegram Invoice (пример)
        from app.telegram_bot.handlers.payments import send_invoice_to_user
        await send_invoice_to_user(update, context)
        return

    elif data == "show_cabinet":
        await show_cabinet(update, context)
        return

    elif data == "back_to_menu":
        from app.telegram_bot.handlers.menu import menu_command
        await menu_command(update, context)
        return

    else:
        # Неизвестная кнопка
        text = "Неизвестная команда кнопки."
        media = InputMediaPhoto(open(cover_path, "rb"), caption=text)
        await query.edit_message_media(media=media)
        return


async def _get_or_create_user(session: AsyncSession, chat_id: int) -> User:
    """
    Вспомогательная функция: находит или создаёт User в БД.
    """
    user_stmt = select(User).where(User.chat_id == chat_id)
    result = await session.execute(user_stmt)
    user = result.scalar_one_or_none()
    if not user:
        user = User(chat_id=chat_id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

# app/telegram_bot/handlers/cabinet.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# Импортируем сервисы
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
    Показывает личный кабинет: баланс пользователя, подписку, кнопки "пополнить" и "история".
    """
    # Определяем chat_id
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        chat_id = query.message.chat.id
    else:
        chat_id = update.effective_chat.id

    # Получаем фабрику сессий (session_factory), которую мы сохранили в bot_data при запуске бота
    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data. Database operations not possible.")
        return

    # Открываем AsyncSession, ищем пользователя, извлекаем баланс и статус подписки
    async with session_factory() as session:
        user = await _get_or_create_user(session, chat_id)
        balance = user.balance_tokens or 0
        subscription_active = user.subscription_status  # bool
        sub_text = "Активна" if subscription_active else "Нет"

    # Формируем текст ответа
    text = (
        f"Личный кабинет\n\n"
        f"UID: `{chat_id}`\n"
        f"Баланс: {balance} токенов\n"
        f"Подписка: {sub_text}\n"
    )

    kb = [
        [InlineKeyboardButton("Пополнить баланс", callback_data="cabinet_topup")],
        [InlineKeyboardButton("История платежей", callback_data="cabinet_history")],
        [InlineKeyboardButton("Назад в меню", callback_data="back_to_menu")]
    ]
    markup = InlineKeyboardMarkup(kb)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=markup, parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=markup, parse_mode="Markdown"
        )

async def cabinet_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Общий callback-хендлер для inline-кнопок в личном кабинете: 
    "Пополнить баланс", "История платежей", "Оплатить через T-Kассу", "Оплатить через Telegram".
    """
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id

    if data == "cabinet_topup":
        kb = [
            [InlineKeyboardButton("Оплатить через T-Кассу", callback_data="cabinet_pay_tkassa"), InlineKeyboardButton("Оплатить через Telegram", callback_data="cabinet_pay_telegram")],
            [InlineKeyboardButton("Назад", callback_data="show_cabinet")]
        ]
        await query.edit_message_text(
            "Выберите способ пополнения:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    elif data == "cabinet_history":
        # Показываем последние 5 транзакций
        session_factory = context.application.bot_data.get("session_factory")
        if not session_factory:
            logger.error("No session_factory found in bot_data.")
            await query.edit_message_text("Ошибка: не можем получить историю (нет подключения к БД).")
            return

        async with session_factory() as session:
            # Предположим, метод get_user_transactions теперь умеет принимать limit
            txns = await get_user_transactions(session, chat_id, limit=5)

        if not txns:
            text = "История платежей пуста."
        else:
            lines = ["Последние транзакции:"]
            for t in txns:
                lines.append(
                    f"• ID {t.id} | {t.amount_rub}₽ => {t.tokens} токенов [{t.status}]"
                )
            text = "\n".join(lines)

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Назад", callback_data="show_cabinet")]
            ])
        )
        return

    elif data == "cabinet_pay_tkassa":
        # Допустим, выставляем 100 руб
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

        # Инициируем платёж через T-Кассу
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
                await query.edit_message_text(
                    f"Не удалось создать платёж: {message}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("Назад", callback_data="show_cabinet")]
                    ])
                )
                return

            payment_url = init_resp.get("PaymentURL")
            text = (
                f"Счёт на {amount_rub}₽ создан!\n"
                f"Транзакция #{txn_id}\n\n"
                f"[Оплатить >>>]({payment_url})"
            )
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Назад", callback_data="show_cabinet")]
                ])
            )

        except Exception as e:
            logger.error(f"Ошибка при init_payment в T-Кассу: {e}", exc_info=True)
            await query.edit_message_text(
                "Ошибка при создании платежа. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Назад", callback_data="show_cabinet")]
                ])
            )
        return

    elif data == "cabinet_pay_telegram":
        # Запускаем Telegram Invoice (из другого модуля handlers.payments)
        from app.telegram_bot.handlers.payments import send_invoice_to_user
        await send_invoice_to_user(update, context)
        return

    elif data == "show_cabinet":
        # Просто возвращаемся в кабинет
        await show_cabinet(update, context)
        return

    elif data == "back_to_menu":
        # Возвращаемся в главное меню
        from app.telegram_bot.handlers.menu import menu_command
        await menu_command(update, context)
        return

    else:
        await query.edit_message_text("Неизвестная команда кнопки.")
        return


# ------------------------------------------------------------------------------
# Вспомогательная функция, чтобы получить пользователя из БД,
# создать его при необходимости
# ------------------------------------------------------------------------------
async def _get_or_create_user(session: AsyncSession, chat_id: int) -> User:
    user_stmt = select(User).where(User.chat_id == chat_id)
    result = await session.execute(user_stmt)
    user = result.scalar_one_or_none()
    if not user:
        user = User(chat_id=chat_id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

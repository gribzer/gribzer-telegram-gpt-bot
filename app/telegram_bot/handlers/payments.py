import logging
from telegram import Update, LabeledPrice
from telegram.ext import ContextTypes
from app.services.payment_service import (
    create_transaction,
    calculate_tokens_for_amount,
    complete_transaction
)

logger = logging.getLogger(__name__)

PROVIDER_TOKEN = "YOUR_PROVIDER_TOKEN"  # получите у провайдера (Stripe/YooKassa/etc.)

async def send_invoice_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Создаём Invoice для оплаты через Telegram.
    """
    query = update.callback_query
    chat_id = update.effective_chat.id  # предпочтительнее, чем query.message.chat.id

    # Допустим, хотим выставить 100 руб
    amount_rub = 100
    tokens = calculate_tokens_for_amount(amount_rub)

    # Берём session_factory из bot_data
    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found in bot_data. Cannot create transaction.")
        await query.edit_message_text("Ошибка: нет подключения к БД.")
        return

    # Создаём транзакцию (status='pending')
    async with session_factory() as session:
        txn = await create_transaction(
            session=session,
            user_id=chat_id,
            amount_rub=amount_rub,
            tokens=tokens,
            method="Telegram"
        )
        txn_id = txn.id

    title = "Пополнение баланса"
    description = f"Транзакция #{txn_id}. {amount_rub} руб."
    prices = [LabeledPrice(label="Баланс", amount=int(amount_rub * 100))]

    # Отправляем Invoice через context.bot
    await context.bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=str(txn_id),  # передаём ID транзакции в payload
        provider_token=PROVIDER_TOKEN,
        currency="RUB",
        prices=prices,
        start_parameter="test-start"
    )


async def pre_checkout_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик запроса перед оплатой (pre-checkout).
    """
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка успешной оплаты.
    """
    payment_info = update.message.successful_payment
    payload = payment_info.invoice_payload  # txn_id в строковом виде
    txn_id = int(payload)

    # Берём session_factory
    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found. Cannot complete transaction.")
        await update.message.reply_text("Ошибка: нет подключения к БД.")
        return

    # Помечаем транзакцию как 'completed' и зачисляем токены
    async with session_factory() as session:
        await complete_transaction(session, txn_id)

    await update.message.reply_text("Оплата успешна! Токены зачислены на ваш баланс.")

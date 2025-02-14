# app/services/payment_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import Transaction, User
import datetime


async def create_transaction(
    session: AsyncSession,
    user_id: int,
    amount_rub: float,
    tokens: float,
    method: str
) -> Transaction:
    """
    Создаёт транзакцию в статусе 'pending'.
    """
    txn = Transaction(
        user_id=user_id,
        amount_rub=amount_rub,
        tokens=tokens,
        payment_method=method,
        status="pending",
        created_at=datetime.datetime.utcnow()
    )
    session.add(txn)
    await session.flush()  # txn.id станет доступен

    # Генерируем order_id на основе ID транзакции
    order_id = f"order-{txn.id}"
    txn.order_id = order_id
    await session.commit()
    await session.refresh(txn)
    return txn


async def update_transaction_successful(session: AsyncSession, txn_id: int):
    """
    Устанавливает статус транзакции в 'completed' и
    зачисляет пользователю tokens на balance_tokens.
    """
    q = select(Transaction).where(Transaction.id == txn_id)
    result = await session.execute(q)
    txn = result.scalar_one_or_none()
    if not txn or txn.status == "completed":
        # Либо транзакция не найдена, либо уже завершена
        return

    txn.status = "completed"

    # Зачисляем юзеру токены
    q_user = select(User).where(User.id == txn.user_id)
    r_user = await session.execute(q_user)
    user = r_user.scalar_one_or_none()
    if user:
        user.balance_tokens = (user.balance_tokens or 0) + (txn.tokens or 0)

    await session.commit()


async def find_transaction_by_order_id(session: AsyncSession, order_id: str) -> Transaction | None:
    """
    Ищет транзакцию по её order_id.
    """
    q = select(Transaction).where(Transaction.order_id == order_id)
    res = await session.execute(q)
    return res.scalar_one_or_none()


async def update_transaction_by_trx_id(session: AsyncSession, txn_id: int, updated_fields: dict):
    """
    Обновляет поля транзакции (по её ID), например {"status": "canceled"}.
    """
    q = select(Transaction).where(Transaction.id == txn_id)
    result = await session.execute(q)
    txn = result.scalar_one_or_none()
    if txn:
        for key, value in updated_fields.items():
            setattr(txn, key, value)
        await session.commit()


async def get_user_transactions(session: AsyncSession, user_id: int) -> list[Transaction]:
    """
    Возвращает список всех транзакций (Transaction) для пользователя user_id.
    """
    stmt = select(Transaction).where(Transaction.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalars().all()


def calculate_tokens_for_amount(amount_rub: float) -> float:
    """
    Конвертирует рубли в токены (пример: 1 рубль = 10 токенов).
    При необходимости измените коэффициент.
    """
    return amount_rub * 10


async def complete_transaction(session: AsyncSession, txn_id: int):
    """
    Аналог update_transaction_successful: ставит транзакцию в 'completed'
    и зачисляет токены пользователю. 
    """
    # Можно просто использовать логику update_transaction_successful:
    await update_transaction_successful(session, txn_id)

from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_async_session
from app.database.models import Transaction
from app.services.payment_service import (
    update_transaction_successful,
    update_transaction_by_trx_id
)

router = APIRouter()

@router.post("/tkassa-webhook")
async def tkassa_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Пример обработки webhook от T-Кассы.
    """
    data = await request.json()

    order_id = data.get("OrderId")
    status = data.get("Status")
    success = data.get("Success", False)

    if not order_id:
        return {"ok": False, "error": "No OrderId"}

    # Ищем транзакцию по order_id
    stmt = select(Transaction).where(Transaction.order_id == order_id)
    result = await session.execute(stmt)
    txn = result.scalars().first()

    if not txn:
        return {"ok": False, "error": "Transaction not found"}

    # Обновляем статус транзакции
    if success and status in ["AUTHORIZED", "CONFIRMED", "COMPLETED"]:
        await update_transaction_successful(session, txn.id)
    elif status in ["CANCELED", "REJECTED"]:
        await update_transaction_by_trx_id(session, txn.id, {"status": "canceled"})

    return {"ok": True}

# app/webhooks/tkassa_webhook.py
import logging
from fastapi import APIRouter, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.payment_service import (
    find_transaction_by_order_id,
    complete_transaction,
    update_transaction_status
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/tkassa-webhook")
async def tkassa_webhook(request: Request, session: AsyncSession):
    """
    Пример обработки webhook от T-Кассы.
    """
    data = await request.json()
    logger.info(f"T-Kassa webhook data: {data}")

    order_id = data.get("OrderId")
    status = data.get("Status")
    success = data.get("Success", False)

    if not order_id:
        return {"ok": False, "error": "No OrderId"}

    txn = await find_transaction_by_order_id(session, order_id)
    if not txn:
        return {"ok": False, "error": "Transaction not found"}

    if success and status in ["AUTHORIZED", "CONFIRMED", "COMPLETED"]:
        await complete_transaction(session, txn.id)
    elif status in ["CANCELED", "REJECTED"]:
        await update_transaction_status(session, txn.id, "canceled")
    else:
        logger.info(f"Transaction {txn.id} status={status}, no action")

    return {"ok": True}

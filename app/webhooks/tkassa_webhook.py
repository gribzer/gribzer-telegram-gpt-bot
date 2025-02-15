import logging
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# ВАЖНО: импортируем get_db_session из app.database.utils, 
# а не из app.main
from app.database.utils import get_db_session

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/tkassa-webhook")
async def tkassa_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Пример обработки webhook от Т-Кассы (Tinkoff).
    """
    data = await request.json()
    logger.info(f"T-Kassa webhook data: {data}")

    order_id = data.get("OrderId")
    status = data.get("Status")
    success = data.get("Success", False)

    if not order_id:
        return {"ok": False, "error": "No OrderId in webhook"}

    # Пример:
    # async with session.begin():
    #     txn = await find_transaction_by_order_id(session, order_id)
    #     ...

    return {"ok": True, "message": f"Webhook processed. OrderId={order_id}, status={status}"}

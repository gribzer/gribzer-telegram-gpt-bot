# app/services/subscription_service.py

import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import User

async def can_use_free_request(session: AsyncSession, user: User) -> bool:
    """
    Проверяет, может ли пользователь сделать бесплатный запрос.
    - Если у пользователя не установлено free_period_start,
      устанавливаем в текущую дату/время и обнуляем free_requests_used.
    - Если сменился месяц (год/месяц отличаются от сохранённого),
      обнуляем счётчик и обновляем free_period_start.
    - Возвращаем True, если free_requests_used < free_requests_limit.
    """
    now = datetime.datetime.now()

    if not user.free_period_start:
        user.free_period_start = now
        user.free_requests_used = 0
        await session.commit()
        return True

    # Если месяц поменялся
    if (user.free_period_start.year != now.year) or (user.free_period_start.month != now.month):
        user.free_period_start = now
        user.free_requests_used = 0
        await session.commit()
        return True

    return user.free_requests_used < user.free_requests_limit

async def increment_free_requests(session: AsyncSession, user: User) -> None:
    """
    Увеличивает счётчик бесплатных запросов на 1 и сохраняет в БД.
    """
    user.free_requests_used += 1
    await session.commit()

async def has_active_subscription(user: User) -> bool:
    """
    Возвращает True, если subscription_status == True
    и, при наличии subscription_expired_at, текущее время < subscription_expired_at.
    Если subscription_expired_at не задана, считаем подписку бессрочной.
    """
    if not user.subscription_status:
        return False
    if not user.subscription_expired_at:
        return True
    return datetime.datetime.now() < user.subscription_expired_at

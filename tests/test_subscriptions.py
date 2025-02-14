# tests/test_subscriptions.py
import pytest
import datetime
from app.database.models import User
from app.services.subscription_service import can_use_free_request, increment_free_requests

@pytest.mark.asyncio
async def test_free_limit(async_session):
    # Создаём юзера
    user = User(chat_id=12345, free_requests_used=49, free_period_start=datetime.datetime.now())
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    can_use = await can_use_free_request(async_session, user)
    assert can_use is True

    await increment_free_requests(async_session, user)
    assert user.free_requests_used == 50

    can_use2 = await can_use_free_request(async_session, user)
    assert can_use2 is False  # лимит исчерпан

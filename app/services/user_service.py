# app/services/user_service.py

import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database.models import User
from app.config import DEFAULT_INSTRUCTIONS

async def get_or_create_user(session: AsyncSession, chat_id: int) -> User:
    """
    Возвращает существующего пользователя (user.chat_id = chat_id),
    либо создаёт нового, если такого ещё нет.
    """
    stmt = select(User).where(User.chat_id == chat_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            chat_id=chat_id,
            selected_model="gpt-3.5-turbo",  # дефолтная модель
            instructions=DEFAULT_INSTRUCTIONS,
            active_chat_id=None,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

async def get_user_model(session: AsyncSession, chat_id: int) -> str | None:
    """
    Возвращает выбранную модель пользователя (user.selected_model).
    """
    stmt = select(User.selected_model).where(User.chat_id == chat_id)
    result = await session.execute(stmt)
    row = result.fetchone()
    return row[0] if row else None

async def set_user_model(session: AsyncSession, chat_id: int, model: str) -> None:
    """
    Устанавливает модель для пользователя (selected_model).
    Создаёт пользователя, если его нет.
    """
    user = await get_or_create_user(session, chat_id)
    user.selected_model = model
    await session.commit()

async def get_user_instructions(session: AsyncSession, chat_id: int) -> str | None:
    """
    Возвращает user.instructions.
    """
    stmt = select(User.instructions).where(User.chat_id == chat_id)
    result = await session.execute(stmt)
    row = result.fetchone()
    return row[0] if row and row[0] else None

async def set_user_instructions(session: AsyncSession, chat_id: int, instructions: str) -> None:
    """
    Устанавливает user.instructions.
    """
    user = await get_or_create_user(session, chat_id)
    user.instructions = instructions
    await session.commit()

async def get_active_chat_id(session: AsyncSession, chat_id: int) -> int | None:
    """
    Возвращает user.active_chat_id.
    """
    stmt = select(User.active_chat_id).where(User.chat_id == chat_id)
    result = await session.execute(stmt)
    row = result.fetchone()
    return row[0] if row else None

async def set_active_chat_id(session: AsyncSession, chat_id: int, chat_db_id: int | None) -> None:
    """
    Устанавливает user.active_chat_id = chat_db_id.
    """
    user = await get_or_create_user(session, chat_id)
    user.active_chat_id = chat_db_id
    await session.commit()

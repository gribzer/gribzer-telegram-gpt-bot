# app/services/chat_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.database.models import Chat, ChatMessage

async def create_chat(session: AsyncSession, user_id: int, title: str) -> Chat:
    """
    Создаёт новый Chat и возвращает объект Chat.
    """
    new_chat = Chat(
        user_id=user_id,
        title=title,
        is_favorite=False
    )
    session.add(new_chat)
    await session.commit()
    await session.refresh(new_chat)
    return new_chat

async def get_user_chats(session: AsyncSession, user_id: int) -> list[Chat]:
    """
    Возвращает все чаты пользователя.
    """
    stmt = select(Chat).where(Chat.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalars().all()

async def get_favorite_chats(session: AsyncSession, user_id: int) -> list[Chat]:
    """
    Возвращает только избранные чаты пользователя.
    """
    stmt = select(Chat).where(Chat.user_id == user_id, Chat.is_favorite == True)
    result = await session.execute(stmt)
    return result.scalars().all()

async def delete_chat(session: AsyncSession, chat_db_id: int) -> None:
    """
    Удаляет ChatMessage для chat_db_id, затем сам Chat.
    (Можно настроить cascade='all,delete-orphan' в models.py)
    """
    # Если у вас cascade в моделях, достаточно удалить сам Chat.
    # Иначе - удаляем сообщения вручную.
    await session.execute(delete(ChatMessage).where(ChatMessage.chat_id == chat_db_id))
    await session.execute(delete(Chat).where(Chat.id == chat_db_id))
    await session.commit()

async def rename_chat(session: AsyncSession, chat_db_id: int, new_title: str) -> None:
    """
    Переименовывает чат (Chat.title = new_title).
    """
    stmt = select(Chat).where(Chat.id == chat_db_id)
    result = await session.execute(stmt)
    chat = result.scalar_one_or_none()
    if chat:
        chat.title = new_title
        await session.commit()

async def set_chat_favorite(session: AsyncSession, chat_db_id: int, is_favorite: bool) -> None:
    """
    Устанавливает is_favorite для чата.
    """
    stmt = select(Chat).where(Chat.id == chat_db_id)
    result = await session.execute(stmt)
    chat = result.scalar_one_or_none()
    if chat:
        chat.is_favorite = is_favorite
        await session.commit()

async def get_chat_title(session: AsyncSession, chat_db_id: int) -> str | None:
    """
    Возвращает название чата, или None, если не найден.
    """
    stmt = select(Chat.title).where(Chat.id == chat_db_id)
    result = await session.execute(stmt)
    row = result.fetchone()
    return row[0] if row else None

async def is_favorite_chat(session: AsyncSession, chat_db_id: int) -> bool:
    """
    Проверяет, является ли чат избранным.
    """
    stmt = select(Chat.is_favorite).where(Chat.id == chat_db_id)
    result = await session.execute(stmt)
    row = result.fetchone()
    return (row[0] == True) if row else False

async def add_message(session: AsyncSession, chat_db_id: int, role: str, content: str) -> None:
    """
    Добавляет новое сообщение (ChatMessage) к чату chat_db_id.
    """
    new_msg = ChatMessage(
        chat_id=chat_db_id,
        role=role,
        content=content
    )
    session.add(new_msg)
    await session.commit()

async def get_chat_messages(session: AsyncSession, chat_db_id: int) -> list[dict]:
    """
    Возвращает список сообщений (role, content) этого чата, в порядке (id ASC).
    """
    stmt = select(ChatMessage).where(ChatMessage.chat_id == chat_db_id).order_by(ChatMessage.id.asc())
    result = await session.execute(stmt)
    rows = result.scalars().all()
    # Преобразуем в list[dict]:
    messages = [
        {"role": row.role, "content": row.content}
        for row in rows
    ]
    return messages

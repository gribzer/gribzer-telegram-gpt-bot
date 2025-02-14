print("=== MAIN STARTED ===")

import logging
import uvicorn
from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from contextlib import asynccontextmanager

from app.config import DB_URL
from app.webhooks.tkassa_webhook import router as tkassa_router
from app.telegram_bot.bot import create_telegram_application

logger = logging.getLogger(__name__)

# 1) Создаём движок и фабрику сессий
engine: AsyncEngine = create_async_engine(DB_URL, echo=False, future=True)
async_session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan-функция (заменяет on_event("startup")/on_event("shutdown")).
    Код до 'yield' выполняется при запуске приложения,
    код после 'yield' - при остановке.
    """
    logger.info("Starting up ...")

    # Если нужно автоматически применять миграции через Alembic:
    # from alembic.config import Config
    # from alembic import command
    # alembic_cfg = Config("alembic.ini")  # путь к вашему файлу
    # command.upgrade(alembic_cfg, "head")

    # Запускаем Telegram-бот (PTB). При необходимости: webhook / polling и т.д.
    application = await create_telegram_application(async_session_factory)
    logger.info("Telegram bot successfully created.")

    yield  # <-- Пока приложение работает

    # При желании можно добавить логику при остановке приложения.
    logger.info("Shutting down ...")


app = FastAPI(
    title="GPT Bot with T-Kassa",
    version="1.0.0",
    description="Пример интеграции Telegram-бота (PTB) и T-Кассы (FastAPI).",
    lifespan=lifespan,  # <-- передаем нашу lifespan-функцию
)

# 2) Подключаем router для T-Касса webhook
app.include_router(tkassa_router, tags=["tkassa"])


@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    """
    Мидлварь FastAPI, которая создаёт AsyncSession для каждого запроса
    и передаёт его в request.state.db_session.
    """
    async with async_session_factory() as session:
        request.state.db_session = session
        response = await call_next(request)
    return response

def get_db_session(request: Request) -> AsyncSession:
    """
    Утилита, чтобы в эндпоинтах (или других местах) получить Session:
    session = get_db_session(request)
    """
    return request.state.db_session


def start():
    """
    Если вы хотите запускать это приложение командой python -m app.main,
    то в разделе `if __name__ == "__main__": start()`.
    """
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False  # Выставьте True, если в режиме разработки
    )

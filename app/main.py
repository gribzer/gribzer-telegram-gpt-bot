import logging
logging.basicConfig(level=logging.INFO)

import uvicorn
from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

from app.config import DB_URL
from app.webhooks.tkassa_webhook import router as tkassa_router  # router
from app.telegram_bot.bot import create_telegram_application
# Импортируем middleware-утилиту из нового файла:
from app.database.utils import get_db_session

logger = logging.getLogger(__name__)

engine = create_async_engine(DB_URL, echo=False, future=True)
async_session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up FastAPI with PTB (polling) ...")
    application = await create_telegram_application(async_session_factory)
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logger.info("Bot polling started...")

    yield

    logger.info("Shutting down PTB...")
    await application.updater.stop()
    await application.stop()
    logger.info("PTB stopped.")

app = FastAPI(lifespan=lifespan)

app.include_router(tkassa_router, tags=["tkassa"])

@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    async with async_session_factory() as session:
        request.state.db_session = session
        response = await call_next(request)
    return response

def start():
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    start()

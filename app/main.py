import logging
logging.basicConfig(level=logging.INFO)

import uvicorn
from fastapi import FastAPI, Request
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from starlette.responses import HTMLResponse

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

from app.config import DB_URL
from app.webhooks.tkassa_webhook import router as tkassa_router
from app.telegram_bot.bot import create_telegram_application
from app.database.utils import get_db_session

# Подключаем SQLAdmin (пакет, ориентированный на FastAPI + SQLAlchemy)
from sqladmin import Admin, ModelView

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# 1) Создаём асинхронный движок и фабрику сессий
# ------------------------------------------------------------------------------
engine = create_async_engine(DB_URL, echo=False, future=True)
async_session_factory = sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# ------------------------------------------------------------------------------
# 2) (Опционально) Объявить ModelView для вашей модели, напр. User.
#    Если у вас есть модель User - раскомментируйте:
# ------------------------------------------------------------------------------
# from app.database.models import User
#
# class UserAdmin(ModelView):
#     model = User
#     # Дополнительные настройки:
#     # column_list = [User.id, User.email, User.created_at]
#     # name = "Пользователи"
#     # icon = "fa-solid fa-users"

# ------------------------------------------------------------------------------
# Lifespan (Startup/Shutdown) — поднимаем PTB и SQLAdmin
# ------------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan-функция:
      - Запускает Telegram-бот (PTB) в режиме polling
      - Настраивает SQLAdmin (админка на /admin)
    """
    logger.info("Starting up FastAPI with PTB (polling)...")

    # 1) Поднимаем Telegram-бот
    application = await create_telegram_application(async_session_factory)
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logger.info("Bot polling started...")

    # 2) Подключаем SQLAdmin на /admin
    admin = Admin(app, engine)
    # Если есть модель:
    # admin.add_view(UserAdmin)

    # Пока приложение работает:
    yield

    # 3) Останавливаем Telegram-бот при завершении приложения
    logger.info("Shutting down PTB...")
    await application.updater.stop()
    await application.stop()
    logger.info("PTB stopped.")

# ------------------------------------------------------------------------------
# Инициализируем FastAPI
# ------------------------------------------------------------------------------
app = FastAPI(lifespan=lifespan)

# Добавляем ProxyHeadersMiddleware, чтобы принятые от Nginx заголовки
# (X-Forwarded-Proto/Port) корректно устанавливали https-ссылки.
app.add_middleware(
    ProxyHeadersMiddleware,
    trusted_hosts=["*"]  # Или укажите конкретно ваш домен/IP
)

# Простейший эндпоинт для проверки главной страницы
@app.get("/", response_class=HTMLResponse)
def root_page():
    return """
    <html>
    <head><title>Gribzer GPT Bot</title></head>
    <body>
      <h1>Welcome to Gribzer GPT Bot</h1>
      <p>Админка: <a href="/admin">/admin</a></p>
    </body>
    </html>
    """

# Подключаем router для T-Касса webhook
app.include_router(tkassa_router, tags=["tkassa"])

# ------------------------------------------------------------------------------
# Мидлварь: создаём AsyncSession на каждый запрос, передаём в request.state.db_session
# ------------------------------------------------------------------------------
@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    async with async_session_factory() as session:
        request.state.db_session = session
        response = await call_next(request)
    return response

# ------------------------------------------------------------------------------
# Точка входа (для локального запуска)
# ------------------------------------------------------------------------------
def start():
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )

if __name__ == "__main__":
    start()

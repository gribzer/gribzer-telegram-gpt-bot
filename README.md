# gribzer-telegram-gpt-bot

Это Telegram-бот, который:

- Поддерживает взаимодействие с нейросетью через Proxy API (или прямой OpenAI).
- Хранит чаты/историю в SQLite (или другой БД через SQLAlchemy).
- Может работать в режиме **Webhook** (через Nginx/HTTPS) или **Polling** (упрощённый).
- Имеет личный кабинет (баланс, платежи) и подключение к T-Кассе / Tinkoff / Telegram Payments.

## 1. Установка и подготовка окружения

### 1.1. Клонировать репозиторий

```bash
git clone https://github.com/gribzer/gribzer-telegram-gpt-bot.git
cd gribzer-telegram-gpt-bot

```

### 1.2. Создать виртуальное окружение и установить зависимости

```bash
python3 -m venv venv
source venv/bin/activate  # (Linux/macOS)
# Windows: venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt

```

> Примечание: если используете async webhook для PTB, убедитесь, что python-telegram-bot[webhooks] тоже установился корректно.
> 

### 1.3. Создать и заполнить файл `.env`

В корне проекта создайте `.env` со значениями ваших ключей. Пример:

```
TELEGRAM_TOKEN=<Ваш_Токен_От_BotFather>
PROXY_API_KEY=<Опционально: Key для Proxy API>

# T-Касса (Tinkoff)
T_KASSA_TERMINAL_KEY=...DEMO
T_KASSA_PASSWORD=...
T_KASSA_SECRET_KEY=...
T_KASSA_API_URL=https://securepay.tinkoff.ru/v2
T_KASSA_IS_TEST=True

DB_URL=sqlite+aiosqlite:///./bot_storage.db

```

Все переменные считываются в `app/config.py`.

### 1.4. (Опционально) Инициализировать или проверить базу (Alembic)

Если вы используете SQLAlchemy + Alembic:

```bash
# Применить миграции (если у вас настроен alembic)
alembic upgrade head

```

Либо, если у вас нет Alembic, — используйте автогенерацию таблиц или другую схему.

---

## 2. Запуск бота напрямую (Polling или Webhook)

### 2.1. Polling (упрощённый)

1. Убедитесь, что в `app/main.py` включено:
    
    ```python
    # По умолчанию проект уже настроен на Lifespan + run_polling
    # через PTB, см. код.
    
    ```
    
2. Запустите:
    
    ```bash
    python -m app.main
    
    ```
    
3. Бот будет опрашивать Telegram в консоли. Подходит для локальной разработки.

### 2.2. Webhook (через Nginx/HTTPS)

1. Настройте Nginx с HTTPS-доменом (например, `gribzergpt.ru`).
2. Прокиньте нужный путь (`/bot`) на локальный порт, где слушает ваш бот.
3. В коде бота (`app/main.py` или `bot.py`) используйте `run_webhook(...)` вместо `run_polling()` (или lifespan-обработку webhook).
4. Запустите:Telegram будет слать запросы на `https://ваш.домен/bot`, Nginx проксирует их к вашему приложению.
    
    ```bash
    python -m app.main
    
    ```
    

---

## 3. Запуск через Docker

1. Установите Docker (см. официальную документацию).
2. В корне проекта проверьте/обновите **Dockerfile** (пример):
    
    ```
    FROM python:3.10-slim
    WORKDIR /app
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    COPY . .
    CMD ["python", "-m", "app.main"]
    
    ```
    
3. Соберите образ:
    
    ```bash
    docker build -t my-bot:latest .
    
    ```
    
4. Запустите контейнер:Проверяйте логи через `docker logs -f my-bot-container`.При webhook + Nginx — Nginx на 443, контейнер слушает 8000.
    
    ```bash
    docker run -d -p 8000:8000 --name my-bot-container my-bot:latest
    
    ```
    

---

## 4. Структура проекта (обновлённая)

Пример (может отличаться в деталях):

```
gribzer-telegram-gpt-bot/
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── config.py          # Загружает .env
│   ├── main.py            # Точка входа (FastAPI + PTB)
│   ├── database/
│   │   ├── __init__.py
│   │   └── models.py      # SQLAlchemy модели
│   ├── services/
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   ├── chat_service.py
│   │   ├── payment_service.py
│   │   └── subscription_service.py
│   ├── telegram_bot/
│   │   ├── __init__.py
│   │   ├── bot.py         # Конфигурирует PTB Application
│   │   ├── handlers/
│   │   │   ├── __init__.py
│   │   │   ├── menu.py            # Главное меню
│   │   │   ├── cabinet.py         # Личный кабинет, оплатa
│   │   │   ├── payments.py        # Telegram Invoices
│   │   │   ├── callbacks.py
│   │   │   ├── conversation.py    # ConversationHandler (new_chat, rename_chat, etc.)
│   │   │   └── message_handler.py
│   │   ├── utils.py
│   │   └── proxyapi_client.py
│   └── webhooks/
│       ├── __init__.py
│       └── tkassa_webhook.py   # Router для T-Кассы (FastAPI)
├── venv/                # Виртуальное окружение (исключено .gitignore)
├── .env                 # Переменные окружения (TELEGRAM_TOKEN, DB_URL, ...)
├── requirements.txt
├── Dockerfile
├── .gitignore
└── README.md

```

---

## 5. Личный кабинет, платежи и T-Касса

- **`handlers/cabinet.py`**:Показывает баланс, историю платежей, кнопки пополнения (через T-Kassa или Telegram Invoice).
- **`payment_service.py`**:Общая логика транзакций (create_transaction, complete_transaction, расчёт токенов за рубли и т. д.).
- **`tkassa_webhook.py`**:Вебхук для уведомлений от T-Кассы (Tinkoff). Приходит JSON с `OrderId`, `Status`, `Success`.
- **`payments.py`**:Логика Telegram-инвойсов (PreCheckoutQuery, successful_payment).

---

## 6. Частые проблемы

1. **ImportError / circular import**
    - Внимательно следите за архитектурой. Если `tkassa_webhook.py` импортирует что-то из `main.py`, а `main.py` импортирует `tkassa_webhook.py`, может возникнуть цикл. Решение: вынести общие функции (например, `get_db_session`) в отдельный модуль (например, `app/database/utils.py`).
2. **PTBUserWarning: If 'per_message=False', 'CallbackQueryHandler' will not be tracked**
    - Если внутри `ConversationHandler` вы хотите ловить `CallbackQueryHandler` «на каждое сообщение», установите `per_message=True`. Если не нужно, можно игнорировать предупреждение.
3. **No OrderId / `Invalid args for response field!`** при FastAPI
    - Убирайте `session: AsyncSession` из сигнатуры эндпоинта, либо используйте `Depends(...)`.

---

## 7. Запуск под systemd (опционально)

Для продакшена можно создать service-файл `/etc/systemd/system/gribzer-gptbot.service`:

```
[Unit]
Description=Gribzer GPT Bot
After=network.target

[Service]
Type=simple
User=<youruser>
WorkingDirectory=/opt/gribzer-telegram-gpt-bot
ExecStart=/opt/gribzer-telegram-gpt-bot/venv/bin/python -m app.main
Restart=always

[Install]
WantedBy=multi-user.target

```

Затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable gribzer-gptbot
sudo systemctl start gribzer-gptbot
systemctl status gribzer-gptbot

```

---

## 8. Краткий список команд бота

- `/start` — Приветственное сообщение.
- `/menu` — Главное меню (inline-кнопки).
- `/cabinet` — Личный кабинет (баланс, платежи, подписка).
- `/help` — Справка.

При желании можете расширять функционал (например, добавить `/newchat`, `/renamechat`), привязать хендлеры в `bot.py`.

---

## 9. Заключение

- **Проект** предоставляет гибкий Telegram-бот (PTB) с FastAPI (в `main.py`) и поддержкой T-Кассы, Telegram Payments, SQLite/Postgres.
- **.env** хранит конфиденциальные переменные (токен бота, ключи T-Кассы, URL БД).
- **Деплой**: либо Docker (контейнер со всем кодом), либо systemd на VPS (с Nginx или polling).
- **Сборка и обновление**:
    - `pip install -r requirements.txt`,
    - `alembic upgrade head` (если миграции),
    - `python -m app.main` или `docker build ...`.
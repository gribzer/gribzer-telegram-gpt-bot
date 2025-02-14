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

> Примечание: если используете async webhook для PTB, убедитесь, что python-telegram-bot[webhooks] установился корректно.
> 

### 1.3. Создать и заполнить файл `.env`

В корне проекта создайте `.env` со значениями ваших ключей:

```
TELEGRAM_TOKEN=<Ваш_Токен_От_BotFather>
PROXY_API_KEY=<Опционально: Key для Proxy API>

# T-Kassa (Тинькофф):
T_KASSA_TERMINAL_KEY=...
T_KASSA_SECRET_KEY=...
T_KASSA_API_URL=https://securepay.tinkoff.ru/v2

# DB_URL, если хотите PostgreSQL или другой движок
DB_URL=sqlite+aiosqlite:///./bot_storage.db

```

Все переменные считываются в `app/config.py`.

### 1.4. (Опционально) Инициализировать или проверить базу (Alembic)

Если вы используете SQLAlchemy + Alembic:

```bash
# Применить миграции, если есть alembic/
alembic upgrade head

```

Либо, если у вас нет Alembic, но осталась поддержка старой `init_db()` (SQLite) — запустите её вручную или удалите.

---

## 2. Запуск бота напрямую (Polling или Webhook)

### 2.1. Polling (упрощённый)

1. В `app/main.py` или `bot.py` замените строку, ответственную за запуск, на что-то вроде:
    
    ```python
    application.run_polling()
    
    ```
    
2. Запустите:или
    
    ```bash
    python -m app.main
    
    ```
    
    ```bash

    python bot.py
    
    ```
    
3. Бот будет опрашивать Telegram. Подходит для локальной разработки.

### 2.2. Webhook (Nginx + SSL)

1. Настройте **Nginx** с HTTPS-доменом (например, `gribzergpt.ru`).
2. Прокиньте `/bot` на локальный порт (см. [пример Nginx-конфига](https://github.com/gribzer/gribzer-telegram-gpt-bot#readme)).
3. Убедитесь, что в `app/main.py` или `bot.py` вызывается:
    
    ```python
    application.run_webhook(
        listen="127.0.0.1",
        port=8000,
        webhook_url="https://gribzergpt.ru/bot"
    )
    
    ```
    
4. Запустите `python bot.py`. Telegram запросы по `https://gribzergpt.ru/bot` будут проксироваться внутрь на `127.0.0.1:8000`.

---

## 3. Запуск через Docker

1. **Установите Docker** (см. Документация).
2. Создайте/обновите файл **Dockerfile** (пример):
    
    ```
    FROM python:3.10-slim
    WORKDIR /app
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    COPY . .
    CMD ["python", "-m", "app.main"]
    
    ```
    
3. **Соберите** образ:
    
    ```bash
    docker build -t my-bot:latest .
    
    ```
    
4. **Запустите** контейнер:
    
    ```bash
    docker run -d -p 8000:8000 --name my-bot-container my-bot:latest
    
    ```
    
    - Если webhook (Nginx) на 443, Docker контейнер слушает 8000, а Nginx проксирует на `127.0.0.1:8000`.

Проверяйте логи:

```bash

docker logs -f my-bot-container

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
│   ├── main.py            # Точка входа (FastAPI или запуск PTB + webhook)
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
│   │   │   ├── menu.py
│   │   │   ├── cabinet.py
│   │   │   ├── payments.py
│   │   │   ├── callbacks.py
│   │   │   ├── conversation.py
│   │   │   └── message_handler.py
│   │   ├── utils.py
│   │   └── proxyapi_client.py
│   └── webhooks/
│       ├── __init__.py
│       └── tkassa_webhook.py   # FastAPI/Flask router для T-Kassa
├── venv/                # Виртуальное окружение (исключено .gitignore)
├── .env                 # Переменные окружения (TELEGRAM_TOKEN, DB_URL, ...)
├── requirements.txt
├── Dockerfile
├── .gitignore
└── README.md

```

---

## 5. Личный кабинет, платежи и T-Касса

- `handlers/cabinet.py` — показывает баланс, историю платежей, кнопки «пополнить через Telegram/T-Kassa».
- `services/payment_service.py` — общие транзакции (create_transaction, complete_transaction), логика расчёта токенов за рубли и т. д.
- `tkassa_webhook.py` — обработка уведомлений от Т-Кассы (через Flask или FastAPI).
- `payments.py` — отправка Telegram Invoice, обработка `successful_payment`.

---

## 6. Запуск как systemd-сервис

Для продакшена можно сделать systemd-юнит `/etc/systemd/system/mygptbot.service`:

```
[Unit]
Description=GPT Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/gribzer-telegram-gpt-bot
ExecStart=/opt/gribzer-telegram-gpt-bot/venv/bin/python /opt/gribzer-telegram-gpt-bot/app/main.py
Restart=always

[Install]
WantedBy=multi-user.target

```

Затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mygptbot
sudo systemctl start mygptbot
systemctl status mygptbot

```

---

## 7. Часто встречающиеся проблемы

1. **Import "X" could not be resolved**
    - Убедитесь, что установлены библиотеки (docker, flask, fastapi, sqlalchemy, и т.п.), а также что в `.env` всё прописано и **VSCode** использует верное виртуальное окружение.
2. **Ошибка SSL** при webhook
    - Настройте Nginx (сертификат Let’s Encrypt). В коде бота укажите `webhook_url="https://<ваш.домен>/bot"`.
3. **OSError: [Errno 98] Address already in use**
    - Порт 8000 уже занят другим процессом. Измените порт или остановите конфликтующий сервис.
4. **SQLite locked**
    - Проверьте, не держит ли какой-то процесс БД в write-режиме. Рекомендуется PostgreSQL, если много пользователей.

---

## 8. Быстрый список команд бота

1. `/start` — Приветствие.
2. `/menu` — Главное меню (чаты, модели, инструкции).
3. `/cabinet` — Личный кабинет (баланс, подписка).
4. `/help` — Справка.

---

## 9. Заключение

- **Структура**: В проекте выделены модули для бота (`telegram_bot`), базы (`database` + Alembic), сервисный слой (`services`), вебхуки (`webhooks`).
- **Конфигурация**: `.env` хранит токены и ключи. `config.py` их загружает.
- **Запуск**: либо напрямую (polling/webhook), либо в Docker, либо под supervisord/systemd.
- **Расширяемость**: можно подключить новые API (GPT/Claude/и т.д.), новые способы оплаты, добавлять подписочные модели.
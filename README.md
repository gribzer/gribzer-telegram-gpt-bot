# gribzer-telegram-gpt-bot

Telegram-бот, использующий GPT (через proxyapi) и хранящий чаты в SQLite. Поддерживает:

1. **Webhook-режим** (через Nginx-прокси на порт 443).
2. **Polling-режим** (для простых тестов без SSL).
3. **Сохранение** истории чатов и инструкций в локальную SQLite-базу.
4. Запуск в виде **systemd-сервиса** (продакшен).
5. При желании — «hot reload» в режиме разработки (через `watchfiles` или `entr`).

## 1. Установка

### 1.1. Клонировать репозиторий

```bash
bash
КопироватьРедактировать
git clone https://github.com/gribzer/gribzer-telegram-gpt-bot.git
cd gribzer-telegram-gpt-bot

```

### 1.2. Создать виртуальное окружение и установить зависимости

```bash
bash
КопироватьРедактировать
python3 -m venv venv
source venv/bin/activate  # (Linux/macOS)
# Для Windows: venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt

```

> Примечание: Для webhook-режима убедитесь, что установлен PTB с поддержкой вебхуков:
> 
> 
> ```bash
> bash
> КопироватьРедактировать
> pip install "python-telegram-bot[webhooks]"
> 
> ```
> 

### 1.3. Настроить переменные окружения (.env)

Создайте файл `.env` в корне проекта со следующим содержимым:

```
dotenv
КопироватьРедактировать
TELEGRAM_TOKEN=<Ваш_Токен_От_BotFather>
PROXY_API_KEY=<Ваш_Key_От_ProxyApi_Если_Нужно_Иначе_Оставьте_Пустым>

```

Это позволит `config.py` считать значения через `os.getenv`.

**Обязательна** переменная `TELEGRAM_TOKEN`. Если `PROXY_API_KEY` не нужен, можно оставить пустым.

---

## 2. Запуск бота

Есть два основных режима: **Webhook** и **Polling**.

### 2.1. Webhook-режим (через Nginx на 443)

**Сценарий**: вы имеете **домен** (например, `gribzergpt.ru`) с валидным SSL-сертификатом (Let’s Encrypt или другой CA), и **Nginx** слушает 443. Nginx проксирует запросы к боту, который внутри слушает локальный порт (например, `127.0.0.1:8000`).

### 2.1.1. Настройка Nginx

Пример минимального конфига (Ubuntu: `/etc/nginx/sites-available/gribzergpt.ru.conf`):

```
nginx
КопироватьРедактировать
server {
    listen 80;
    server_name gribzergpt.ru;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name gribzergpt.ru;

    ssl_certificate /etc/letsencrypt/live/gribzergpt.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/gribzergpt.ru/privkey.pem;

    # Прокидываем пути /bot (или любой другой) -> локальный порт 8000
    location /bot {
        proxy_pass http://127.0.0.1:8000/;  # обязательно со слешем в конце
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

```

Перезагрузите Nginx:

```bash
bash
КопироватьРедактировать
sudo nginx -t
sudo systemctl reload nginx

```

Теперь все запросы на `https://gribzergpt.ru/bot` будут перенаправляться на `127.0.0.1:8000/`.

### 2.1.2. Правка `bot.py`

Убедитесь, что в финальном коде `bot.py` есть:

```python
python
КопироватьРедактировать
application.run_webhook(
    listen="127.0.0.1",
    port=8000,
    webhook_url="https://gribzergpt.ru/bot",  # публичный URL, который Telegram будет вызывать
)

```

> Обратите внимание:
> 
> - **Нет** `cert=...`/`key=...`, SSL занимается Nginx.
> - `listen="127.0.0.1"` — слушает локальный адрес (безопасно).
> - `"/bot"` в конце webhook_url совпадает с `location /bot` в Nginx.

### 2.1.3. Запуск

```bash
bash
КопироватьРедактировать
python bot.py

```

или

```bash
bash
КопироватьРедактировать
python3 bot.py

```

В логах увидите что-то вроде:

```
nginx
КопироватьРедактировать
INFO - Starting webhook mode on 127.0.0.1:8000 (proxied by Nginx on 443)...
INFO - Application started

```

Проверить:

```bash
bash
КопироватьРедактировать
curl "https://api.telegram.org/bot<Токен>/getWebhookInfo"

```

В `result.url` должно быть `https://gribzergpt.ru/bot`, не 404. Теперь при отправке `/start` в Телеграм-бот — должно работать.

---

### 2.2. Polling-режим (упрощённый)

Если не хотите морочиться с SSL и Nginx, можно включить **polling**. Достаточно **заменить** в `bot.py` строку:

```python
python
КопироватьРедактировать
application.run_polling()

```

и убрать вызовы `run_webhook`. Запускаете:

```bash
bash
КопироватьРедактировать
python bot.py

```

В консоли бот будет опрашивать Telegram-сервер раз в несколько секунд, и вы сразу сможете тестировать `/start`, `menu`, т.д. Но при этом **не нужен** никакой веб-сервер и сертификат.

---

## 3. Автоматический запуск (systemd-сервис)

Для **продакшена** удобно, чтобы бот автоматически запускался при старте сервера. Пример юнит-файла: `/etc/systemd/system/gptbot.service`:

```
ini
КопироватьРедактировать
[Unit]
Description=GPT Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/telegram_bot
ExecStart=/opt/telegram_bot/venv/bin/python3 /opt/telegram_bot/bot.py
Restart=always

# Можно указать User=telegrambot (предварительно создав такого пользователя)

[Install]
WantedBy=multi-user.target

```

Затем:

```bash
bash
КопироватьРедактировать
sudo systemctl daemon-reload
sudo systemctl enable gptbot
sudo systemctl start gptbot
systemctl status gptbot

```

Если всё в порядке, получите `Active: active (running)`. Лог смотреть:

```bash
bash
КопироватьРедактировать
journalctl -u gptbot -f

```

При обновлении кода выполните:

```bash
bash
КопироватьРедактировать
sudo systemctl restart gptbot

```

---

## 4. Hot Reload при разработке

Systemd **не** умеет нативно отслеживать изменения файлов и перезапускать процесс. Для **быстрой разработки** без ручного рестарта можно использовать инструменты:

- [**watchfiles**](https://github.com/samuelcolvin/watchfiles)
    
    ```bash
    bash
    КопироватьРедактировать
    pip install watchfiles
    python -m watchfiles --python=bot.py .
    
    ```
    
    При любом изменении `.py`-файла бот перезапустится автоматически.
    
- **entr**
    
    ```bash
    bash
    КопироватьРедактировать
    ls *.py handlers/*.py | entr -r python3 bot.py
    
    ```
    
    Аналогичный принцип.
    

> В продакшене, наоборот, предпочитают статичный запуск через systemd и делают обновления вручную (deploy + systemctl restart).
> 

---

## 5. Особые моменты

1. **Переменные окружения**: кроме `TELEGRAM_TOKEN`, можно задать `PROXY_API_KEY`. Если вы не используете внешний proxyapi, оставьте пустым.
2. **Пер_MESSAGE_WARNINGS**:
    
    Вы можете видеть предупреждения вроде:
    
    ```
    rust
    КопироватьРедактировать
    PTBUserWarning: If 'per_message=False', 'CallbackQueryHandler' will not be tracked for every message.
    
    ```
    
    Это не фатально. Если для ConversationHandler вас устраивает поведение `per_message=False`, можно игнорировать предупреждения. Или сделать `per_message=True`, но тогда все обработчики должны быть `CallbackQueryHandler`.
    
3. **Database**: По умолчанию бот хранит данные в `bot_storage.db` (см. `DB_PATH` в `config.py`). Убедитесь, что у процесса есть права на запись.
4. **Обновление кода**: При каждом изменении логики нужно перезапустить бот (или настроить hot reload в dev-режиме).

---

## 6. Структура проекта (кратко)

- `bot.py`: Точка входа (запуск бота, регистрация хендлеров, webhook или polling).
- `config.py`: Чтение `.env`, базовые настройки.
- `db.py`: Логика инициализации/апгрейда SQLite.
- `handlers/`: Модули-обработчики:
    - `menu.py`, `callbacks.py`, `conversation.py`, ...
- `handle_message.py`: Обработка текстовых сообщений.

---

## 7. Быстрый старт

1. Склонировать репо и установить зависимости.
2. Создать `.env` с `TELEGRAM_TOKEN=...`.
3. (Опционально) Настроить Nginx + SSL, если хотите webhook. Иначе используйте `run_polling()`.
4. Запустить:
    
    ```bash
    bash
    КопироватьРедактировать
    python bot.py
    
    ```
    
5. Открыть Telegram, найти бота, ввести `/start`. Должен отвечать.

Если что-то не работает, смотрите логи в консоли или `journalctl -u <service>`.
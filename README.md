# Gribzer Telegram GPT Bot

Gribzer Telegram GPT Bot — это бот для Telegram, использующий GPT-модели (через [ProxyAPI](https://proxyapi.ru/docs)) для генерации ответов на сообщения пользователей.  
Проект позволяет обходить ограничение OpenAI в России, используя прокси-сервис ProxyAPI, при этом максимально сохраняется совместимость с официальными методами OpenAI API.

## Основные возможности

1. **Переключение моделей**: пользователь может выбрать одну из заранее заданных моделей (например, gpt-4o, o1, o3-mini) или подставить любую другую, если логика позволяет.  
2. **Механизм чатов**: бот хранит несколько чатов на каждого пользователя (поддержка избранных, переименование, просмотр истории).  
3. **Инструкции (Prompts)**: можно задать «инструкцию» или «контекст» для улучшения ответов модели.  
4. **Гибкая архитектура**: использование `handlers/` для раздельной логики меню, колбэков, conversation flows, хранение данных в локальной базе, а также гибкая интеграция через `proxyapi_client`.  
5. **Возможность работы через webhook** (с SSL-доменом) или polling.

## Структура проекта

Основные файлы и папки:

```
gribzer-telegram-gpt-bot/
├── bot.py                  # Точка входа: запуск бота (webhook или polling), регистрация хендлеров
├── config.py               # Общие настройки: токены, ProxyAPI key, таймауты, пути к БД
├── db.py                   # Логика БД (инициализация, апгрейд, CRUD для чатов, моделей, инструкций)
├── proxyapi_client.py      # Модуль для обращения к ProxyAPI (chat completions, models, embeddings и т.д.)
├── handle_message.py       # Логика обработки входящих текстовых сообщений (не команд)
├── handlers/
│   ├── menu.py             # Команды /start, /menu, /help. Формирование главного меню (inline-кнопки)
│   ├── callbacks.py        # Обработка callback_data (inline-кнопок): смена модели, история чата, инструкции и т.д.
│   ├── chats.py            # Логика вывода списка чатов, избранных, истории
│   └── conversation.py     # Определение ConversationHandler для инструкций, нового чата и др.
├── requirements.txt        # Список зависимостей
├── .env                    # Файл с переменными окружения (TELEGRAM_BOT_TOKEN, PROXY_API_KEY и т.д.)
├── README.md               # Текущее руководство
└── LICENSE                 # Лицензия MIT
```

Ниже — детальные пояснения по каждому модулю.

### 1. bot.py

- **Назначение**: точка входа. Здесь запускается приложение Telegram, регистрируются все хендлеры (команды, callback query, conversation), и выбирается способ работы:
  - **polling** (через `application.run_polling()`)
  - **webhook** (через `application.run_webhook()`)
- **on_startup**: при необходимости (особенно для webhook) здесь вызываются асинхронные действия, вроде `setMyCommands`, `setChatMenuButton`.
- **Пример** (polling):

  ```python
  if __name__ == "__main__":
      main()  # init_db(); upgrade_db(); application.run_polling()
  ```

- **Пример** (webhook):

  ```python
  application.run_webhook(
      listen="127.0.0.1",
      port=8000,
      webhook_url="https://ваш-домен/<TOKEN>"
  )
  ```

### 2. config.py

- **Хранение конфигурации**:
  - Считывает `.env` (через `python-dotenv`) для переменных `TELEGRAM_BOT_TOKEN`, `PROXY_API_KEY`.
  - Хранит `TIMEOUT` для HTTP-запросов, параметры БД, другие константы (например, размер страницы, лимиты и т.д.).
- **Пример**:

  ```python
  import os
  from dotenv import load_dotenv
  load_dotenv()
  
  TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
  PROXY_API_KEY = os.getenv("PROXY_API_KEY")
  DB_PATH = "bot_storage.db"
  ```

### 3. db.py

- **Инициализация БД**: функции `init_db()` и `upgrade_db()` создают необходимые таблицы (чаты, модели, инструкции и т. д.) и выполняют миграции.
- **CRUD-функции**: например, `set_user_model(chat_id, model)`, `get_active_chat_id(user_id)`, `delete_chat(chat_db_id)` и т. п.
- Использует либо `sqlite3`, либо другую СУБД (зависит от реализации).

---

### 4. proxyapi_client.py

- **Назначение**: единая точка для общения с `ProxyAPI`.
  - Методы: `fetch_available_models()`, `create_chat_completion(...)`, `create_embedding(...)`, `upload_file(...)` и т. д.
  - Внутри формируется `BASE_URL = "https://api.proxyapi.ru/openai/v1"`, заголовки `Authorization: Bearer <PROXY_API_KEY>` и отправляются запросы через `httpx`.
- **Глобальный кэш**: при желании можно хранить список моделей `AVAILABLE_MODELS` и инициализировать их вызовом `init_available_models()`.

---

### 5. handle_message.py

- **Логика обработки** обычных текстовых сообщений (не команд).
- Например, если пользователь просто пишет, бот берёт текущую модель (через `get_user_model(chat_id)`) и формирует запрос в `proxyapi_client.create_chat_completion(...)`, затем возвращает ответ в чат.

---

### 6. Папка handlers/

Разделена на несколько модулей по смыслу:

### 1. menu.py
   - Обрабатывает команды `/start`, `/menu`, `/help`.
   - Формирует инлайн-клавиатуру главного меню (кнопки "Все чаты", "Избранные чаты", "Сменить модель", "Инструкции", "История" и т. п.).
   - Обычно при `/start` высылает приветственное сообщение и упоминает: "Нажмите /menu или используйте встроенную кнопку меню Telegram".

### 2. callbacks.py
   - Главный обработчик inline-кнопок через `button_handler`.
   - Смотрит на `callback_data` (`"all_chats"`, `"favorite_chats"`, `"change_model"`, `"model_gpt-4o"` и т. д.) и вызывает соответствующие функции.
   - Именно здесь реализована логика "Выбрать модель": при нажатии "Сменить модель" появляется список заранее заданных моделей (например, `["gpt-4o", "o1", "o3-mini"]`), а при выборе сохраняется в БД.
   - Здесь же "История текущего чата", "Удалить инструкции" и т. д.

### 3. chats.py
   - Функции для показа всех чатов (`show_all_chats_list`), любимых чатов (`show_favorite_chats_list`), истории чата (`show_chat_history`) и т. п.
   - Вызывается из `callbacks.py`.

### 4. conversation.py
   - Содержит описания `ConversationHandler` или специальные хендлеры для "пошаговых" сценариев:
     - Добавление / редактирование инструкций (меню инструкций).
     - Создание / переименование чата.
   - Включает константы состояния (`SET_INSTRUCTIONS`, `SET_NEW_CHAT_TITLE`, `SET_RENAME_CHAT`, `INSTRUCTIONS_INPUT`).

Таким образом, в `handlers/` сконцентрирован код, связанный с Telegram-хендлерами (команды, инлайн-кнопки, `conversation`).

---

## Установка и запуск

### 1. Клонируйте репозиторий:

```bash
git clone https://github.com/gribzer/gribzer-telegram-gpt-bot.git
cd gribzer-telegram-gpt-bot
```

### 2. Установите зависимости:

```bash
pip install -r requirements.txt
```

Убедитесь, что используется Python 3.7+.

### 3. Настройте переменные окружения:

Создайте файл `.env`:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
PROXY_API_KEY=your_proxy_api_key
```

Можно также добавить настройки для webhook (домен, пути к SSL-файлам), если запускаетесь напрямую на HTTPS.

### 4. Инициализируйте БД (опционально, если используется SQLite внутри):

- При запуске `python bot.py` произойдёт вызов `init_db()` и `upgrade_db()`.
- В файле `config.py` или `db.py` может быть путь `DB_PATH = "bot_storage.db"`.

### 5. Запуск бота:

- **Через long polling** (по умолчанию в `bot.py`):

  ```bash
  python bot.py
  ```
  
  Бот запустится и будет опрашивать Telegram-сервер.

- **Через webhook**:
  - Настройте SSL и домен (см. ниже).
  - В `bot.py` вместо `run_polling()` вызовите `run_webhook(...)`, указав `webhook_url="https://ваш-домен/..."`
  - Запустите `python bot.py`. Теперь Telegram будет слать обновления по HTTPS.

---

## Запуск бота через webhook (с SSL и доменом)

### Краткая инструкция:

1. **Настройте домен** (например, `gribzergpt.ru`) и укажите в DNS на IP вашего сервера.
2. **Установите Nginx** и **Let’s Encrypt** (`certbot`) для получения SSL-сертификата.
3. **Настройте reverse-proxy**: Nginx принимает `https://gribzergpt.ru/<PATH>` и пересылает на ваше Python-приложение, которое слушает `127.0.0.1:8000`.
4. **В `bot.py` используйте**:

   ```python
   application.run_webhook(
       listen="127.0.0.1",
       port=8000,
       webhook_url="https://gribzergpt.ru/BOT_PATH"
   )
   ```

   PTB автоматически вызовет `setWebhook` на Telegram Bot API.

5. Telegram начнёт присылать апдейты на `https://gribzergpt.ru/BOT_PATH`.

См. подробнее в разделе "Issues" или документации Telegram Bot API (и в нашем проекте есть отдельные инструкции/подсказки в коде).

# Gribzer Telegram GPT Bot

## Использование бота

### Команды (через Telegram-меню)

- `/start`: Приветственное сообщение.
- `/menu`: Вызывает главное меню (инлайн-кнопки).
- `/help`: Вывод справки.

### Главное меню

При `/menu` появляется инлайн-клавиатура:
- **Все чаты / Избранные чаты**: выводит списки доступных чатов пользователя.
- **Сменить модель**: открывает кнопки выбора моделей (по умолчанию: `gpt-4o`, `o1`, `o3-mini`).
- **Инструкции**: позволяет добавить/редактировать «общие инструкции».
- **История**: показывает историю текущего (активного) чата.
- **Помощь**: краткая справка.

### Переключение модели

При выборе «Сменить модель» бот выводит несколько кнопок (заранее заданных). Пользователь нажимает, и та модель привязывается к текущему пользователю/чату (по логике `set_user_model`). Все дальнейшие сообщения к GPT будут отправляться с `model=<выбранная_модель>`.

### Механизм чатов

- Можно создать новый чат (например, для новой темы разговора).
- Можно сделать чат избранным (⭐), переименовать, удалить.
- Просмотреть историю.

### Инструкции (Prompts)

- Можно добавить/редактировать общие инструкции, которые будут «добавляться» к каждому запросу. Удобно, чтобы задать общий стиль ответов или формат.

---

## Работа с ProxyAPI

Сервис [ProxyAPI](https://proxyapi.ru/) позволяет отправлять запросы к OpenAI (и другим сервисам) из России.

- `PROXY_API_KEY` (в `.env`) необходим для авторизации.
- В модуле `proxyapi_client.py` формируется запрос вида:

  ```python
  response = client.post(
      "https://api.proxyapi.ru/openai/v1/chat/completions",
      headers={ "Authorization": f"Bearer {PROXY_API_KEY}" },
      json=payload
  )
  ```

- Документация: [proxyapi.ru/docs](https://proxyapi.ru/docs).

---

## Дополнительно

### Автоматический запуск (systemd)

Для продакшена удобно запускать бота как сервис:

Файл `/etc/systemd/system/mybot.service`:

```ini
[Unit]
Description=My Telegram GPT Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/gribzer-telegram-gpt-bot
ExecStart=/opt/gribzer-telegram-gpt-bot/venv/bin/python bot.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Затем выполните команды:

```sh
sudo systemctl daemon-reload
sudo systemctl enable mybot
sudo systemctl start mybot
```

### Docker (опционально)

При желании можно упаковать в `Dockerfile` (не входит в базовый проект). Нужно лишь скопировать всё, установить зависимости и запустить `bot.py`.

---

## Лицензия

Проект распространяется под лицензией [MIT](LICENSE).

---

## Контакты / Обратная связь

- Вопросы по ProxyAPI: [contact@proxyapi.ru](mailto:contact@proxyapi.ru)
- Pull Requests и Issues принимаются в [репозитории](https://github.com/gribzer/gribzer-telegram-gpt-bot).
- Бот находится в активной разработке. Будем рады любому вкладу!

Спасибо за использование **Gribzer Telegram GPT Bot**! Будем рады вашим замечаниям и предложениям.


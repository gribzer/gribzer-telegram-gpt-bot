# Используем официальный Python образ
FROM python:3.10-slim

# Создадим директорию для проекта
WORKDIR /app

# Скопируем файлы requirements.txt (или pyproject.toml, если используете Poetry)
# в контейнер и установим зависимости
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Скопируем всё содержимое проекта (включая app/, alembic/, и т.д.) в контейнер
COPY . .

# Если вам нужно применить миграции Alembic автоматически:
# RUN alembic upgrade head

# Запускаем вашу основную команду (FastAPI или Telegram bot + webhook)
# Допустим, вы хотите запустить FastAPI (app/main.py), который на 8000 порту:
CMD ["python", "-m", "app.main"]

# Если же у вас нет FastAPI, а только Telegram bot на webhook или polling, 
# замените последнюю команду на нужную:
# CMD ["python", "-m", "app.telegram_bot.bot"]


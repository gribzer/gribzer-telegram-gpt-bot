import asyncio
import logging

from telegram import BotCommand, MenuButtonCommands
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)
from config import TELEGRAM_TOKEN
from db import init_db, upgrade_db
from handlers.menu import start_command, menu_command, help_command
from handlers.callbacks import button_handler
from handlers.conversation import (
    instructions_add_entry,
    instructions_edit_entry,
    instructions_input_finish,
    INSTRUCTIONS_INPUT,

    new_chat_entry,
    set_new_chat_title,
    rename_chat_entry,
    rename_chat_finish,
    SET_NEW_CHAT_TITLE,
    SET_RENAME_CHAT
)
from handle_message import handle_user_message

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    # 1. Инициализируем БД
    init_db()
    upgrade_db()

    # 2. Создаём приложение Telegram
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 3. Регистрируем хендлеры (команды, conversation и т.д.)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))

    new_chat_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_chat_entry, pattern="^new_chat$")],
        states={
            SET_NEW_CHAT_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_chat_title),
            ]
        },
        fallbacks=[]
    )
    application.add_handler(new_chat_conv_handler)

    rename_chat_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(rename_chat_entry, pattern=r"^rename_\d+$")],
        states={
            SET_RENAME_CHAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rename_chat_finish),
            ]
        },
        fallbacks=[]
    )
    application.add_handler(rename_chat_conv_handler)

    instructions_manage_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(instructions_add_entry, pattern="^instructions_add$"),
            CallbackQueryHandler(instructions_edit_entry, pattern="^instructions_edit$")
        ],
        states={
            INSTRUCTIONS_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, instructions_input_finish)
            ]
        },
        fallbacks=[]
    )
    application.add_handler(instructions_manage_conv_handler)

    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))

    # 4. Опционально: устанавливаем команды бота и кнопку меню (до запуска webhook)
    #    Так как set_my_commands и set_chat_menu_button - асинхронные,
    #    мы вызовем их напрямую через event loop.
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("menu", "Показать главное меню"),
        BotCommand("help", "Справка о боте"),
    ]

    async def setup_bot_commands():
        await application.bot.set_my_commands(commands)
        await application.bot.set_chat_menu_button(MenuButtonCommands())
        logger.info("Команды бота и кнопка меню установлены.")

    # Выполним асинхронно в текущем (глобальном) event loop
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup_bot_commands())

    # 5. Запускаем Webhook
    #    Если слушаем напрямую порт 443, нужны права root или setcap на Python
    #    Если используете Nginx-прокси, можно listen=127.0.0.1:8000 + проксирование
    ssl_cert = "/etc/letsencrypt/live/gribzergpt.ru/fullchain.pem"
    ssl_priv = "/etc/letsencrypt/live/gribzergpt.ru/privkey.pem"

    webhook_url = f"https://gribzergpt.ru/{TELEGRAM_TOKEN}"  # уже установлен в Telegram

    logger.info("Starting webhook mode...")
    application.run_webhook(
        listen="0.0.0.0",
        port=443,
        cert=ssl_cert,  # PTB v20: 'cert' вместо 'ssl_cert'
        key=ssl_priv,   # PTB v20: 'key' вместо 'ssl_key'
        webhook_url=webhook_url,
    )


if __name__ == "__main__":
    main()

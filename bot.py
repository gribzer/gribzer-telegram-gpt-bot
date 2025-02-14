import logging
from telegram import BotCommand, MenuButtonCommands
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
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


async def on_startup(application):
    """
    Функция, вызываемая при старте (уже в event loop). Здесь:
    - Устанавливаем команды, чтобы они отображались в меню (синяя кнопка).
    """
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("menu", "Показать главное меню"),
        BotCommand("help", "Справка о боте"),
    ]
    await application.bot.set_my_commands(commands)
    # Установим кнопку меню (необязательно)
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    logger.info("on_startup: команды бота установлены.")


def main():
    # 1. Инициализация БД
    init_db()
    upgrade_db()

    # 2. Создаём приложение
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 3. Регистрируем хендлеры
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

    # 4. Запуск вебхука (Application.run_webhook)
    #    - listen: на каком IP слушаем
    #    - port:    на каком порту
    #    - webhook_url: тот URL, на который Telegram будет слать апдейты
    #    - key и cert: ваш SSL (если запускаетесь напрямую на 443)
    #    - on_startup: вызывается после запуска event loop, но до принятия апдейтов

    # Путь к вашему .pem/.key (Let’s Encrypt, например)
    ssl_cert = "/etc/letsencrypt/live/gribzergpt.ru/fullchain.pem" 
    ssl_priv = "/etc/letsencrypt/live/gribzergpt.ru/privkey.pem"

    # Полный URL, куда Telegram будет отправлять запросы (обратите внимание на /TOKEN)
    webhook_url = f"https://gribzergpt.ru/{TELEGRAM_TOKEN}"

    logger.info("Starting webhook mode...")
    application.run_webhook(
        listen="0.0.0.0",
        port=443,
        webhook_url=webhook_url,
        ssl_cert=ssl_cert,
        ssl_key=ssl_priv,
        on_startup=on_startup,
    )


if __name__ == "__main__":
    main()

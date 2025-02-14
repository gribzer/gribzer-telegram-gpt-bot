# app/telegram_bot/bot.py

import logging
from telegram import BotCommand, MenuButtonCommands
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    PreCheckoutQueryHandler,
    filters
)

from app.config import TELEGRAM_TOKEN
from app.telegram_bot.handlers.menu import start_command, menu_command, help_command
from app.telegram_bot.handlers.cabinet import show_cabinet, cabinet_callback_handler
from app.telegram_bot.handlers.payments import pre_checkout_query_handler, successful_payment_handler
from app.telegram_bot.handlers.callback_general import button_handler
from app.telegram_bot.handlers.conversation import (
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
from app.telegram_bot.handlers.message_handler import handle_user_message

logger = logging.getLogger(__name__)


async def create_telegram_application(session_factory=None) -> Application:
    """
    Создаёт и настраивает экземпляр PTB Application (Telegram-бот).
    :param session_factory: (опционально) фабрика AsyncSession, 
                            если вам нужно работать с БД из хендлеров.
    :return: сконфигурированный объект Application, который можно 
             запускать (polling или webhook) в другом месте.
    """

    # 1. Создаём приложение PTB
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Если нужно передавать session_factory (SQLAlchemy) в хендлеры,
    # можем хранить его в bot_data:
    if session_factory:
        application.bot_data["session_factory"] = session_factory

    # 2. Регистрируем команды/хендлеры
    # --------------------------------

    # Команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cabinet", show_cabinet))

    # Личный кабинет (callback)
    application.add_handler(CallbackQueryHandler(cabinet_callback_handler, pattern="^cabinet_|^show_cabinet"))

    # Telegram Payments
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_query_handler))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))

    # ConversationHandlers (например, создание/переименование чата)
    new_chat_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_chat_entry, pattern="^new_chat$")],
        states={
            SET_NEW_CHAT_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_chat_title),
            ]
        },
        fallbacks=[],
    )
    application.add_handler(new_chat_conv_handler)

    rename_chat_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(rename_chat_entry, pattern=r"^rename_\d+$")],
        states={
            SET_RENAME_CHAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rename_chat_finish),
            ]
        },
        fallbacks=[],
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
        fallbacks=[],
    )
    application.add_handler(instructions_manage_conv_handler)

    # Общий CallbackQueryHandler (на всё остальное)
    application.add_handler(CallbackQueryHandler(button_handler))

    # Хендлер на обычное текстовое сообщение
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))

    # 3. Регистрируем команды и меню
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("menu", "Показать главное меню"),
        BotCommand("help", "Справка о боте"),
        BotCommand("cabinet", "Личный кабинет")
    ]

    # Устанавливаем команды и кнопку меню
    async def setup_bot_commands(app: Application):
        await app.bot.set_my_commands(commands)
        await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Команды бота и кнопка меню установлены.")

    # Вызываем настройку команд немедленно (либо по желанию после .startup())
    await setup_bot_commands(application)

    # 4. Возвращаем готовое приложение
    logger.info("Telegram application (bot) создан и настроен.")
    return application

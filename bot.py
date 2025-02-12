# bot.py
import logging
import httpx

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)

from config import TELEGRAM_TOKEN
from db import init_db, upgrade_db
from handlers.menu import start_command, menu_command
from handlers.callbacks import button_handler
from handlers.conversation import (
    # Старый вариант:
    update_instructions_entry,
    receive_instructions,
    SET_INSTRUCTIONS,

    # Новый вариант (меню инструкций):
    instructions_add_entry,
    instructions_edit_entry,
    instructions_input_finish,
    INSTRUCTIONS_INPUT,

    # Для чатов:
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
    init_db()
    upgrade_db()

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # 1) ConversationHandler: инструкции (старый метод)
    instructions_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(update_instructions_entry, pattern="^update_instructions$")],
        states={
            SET_INSTRUCTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_instructions)
            ]
        },
        fallbacks=[],
        map_to_parent={},
    )

    # 2) ConversationHandler: создание нового чата
    new_chat_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_chat_entry, pattern="^new_chat$")],
        states={
            SET_NEW_CHAT_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_chat_title),
            ]
        },
        fallbacks=[],
        map_to_parent={},
    )

    # 3) ConversationHandler: переименование чата
    rename_chat_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(rename_chat_entry, pattern=r"^rename_\d+$")],
        states={
            SET_RENAME_CHAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rename_chat_finish),
            ]
        },
        fallbacks=[],
        map_to_parent={},
    )

    # 4) Новый ConversationHandler для «меню инструкций» (Добавить/Редактировать)
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

    # Регистрируем
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))

    application.add_handler(instructions_conv_handler)       # Старый
    application.add_handler(new_chat_conv_handler)           # Создание чата
    application.add_handler(rename_chat_conv_handler)         # Переименование чата
    application.add_handler(instructions_manage_conv_handler) # Меню инструкций (новое)

    # Инлайн-кнопки (button_handler) ловит всё остальное
    application.add_handler(CallbackQueryHandler(button_handler))

    # Текстовые сообщения
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))

    application.run_polling()


if __name__ == '__main__':
    main()

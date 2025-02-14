# app/telegram_bot/handlers/callback_general.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

# Предположим, вы создали user_service и chat_service:
# user_service.py:
#   async def get_user_instructions(session: AsyncSession, chat_id: int) -> str: ...
#   async def set_user_instructions(session: AsyncSession, chat_id: int, text: str) -> None: ...
#   async def set_user_model(session: AsyncSession, chat_id: int, model: str) -> None: ...
#   async def get_user_model(session: AsyncSession, chat_id: int) -> str: ...
#   async def get_active_chat_id(session: AsyncSession, chat_id: int) -> int: ...
#   async def set_active_chat_id(session: AsyncSession, chat_id: int, chat_db_id: int) -> None: ...
#
# chat_service.py:
#   async def delete_chat(session: AsyncSession, chat_db_id: int) -> None: ...
#   async def set_chat_favorite(session: AsyncSession, chat_db_id: int, is_fav: bool) -> None: ...
#
from app.services.user_service import (
    get_user_instructions,
    set_user_instructions,
    set_user_model,
    get_user_model,
    get_active_chat_id,
    set_active_chat_id
)
from app.services.chat_service import (
    delete_chat,
    set_chat_favorite
)

# Импорт хендлеров
from app.telegram_bot.handlers.menu import menu_command
from app.telegram_bot.handlers.chats import (
    show_all_chats_list,
    show_favorite_chats_list,
    show_single_chat_menu,
    show_chat_history
)
from app.telegram_bot.handlers.conversation import (
    rename_chat_entry,
    new_chat_entry,
    instructions_add_entry,
    instructions_edit_entry
)

# Если используете ConversationHandler, импортируйте состояния:
from app.config import (
    SET_INSTRUCTIONS,
    SET_NEW_CHAT_TITLE,
    SET_RENAME_CHAT
)

logger = logging.getLogger(__name__)

async def instructions_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает "Меню инструкций": текущие инструкции, кнопки "редактировать / удалить / добавить".
    """
    query = update.callback_query
    chat_id = query.message.chat.id

    # Берём session_factory
    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found. Can't load instructions.")
        await query.edit_message_text("Ошибка: нет подключения к БД.")
        return

    async with session_factory() as session:
        current_instructions = await get_user_instructions(session, chat_id)
        current_instructions = current_instructions or ""
    is_empty = not current_instructions.strip()

    if is_empty:
        text = "Текущие инструкции: (пусто)"
        keyboard = [[InlineKeyboardButton("Добавить инструкции", callback_data="instructions_add")]]
    else:
        text = f"Текущие инструкции:\n\n{current_instructions}"
        keyboard = [[
            InlineKeyboardButton("Редактировать инструкции", callback_data="instructions_edit"),
            InlineKeyboardButton("Удалить", callback_data="instructions_delete")
        ]]

    keyboard.append([InlineKeyboardButton("В меню", callback_data="back_to_menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def instructions_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Удаление (очистка) инструкций у пользователя.
    """
    query = update.callback_query
    chat_id = query.message.chat.id

    session_factory = context.application.bot_data.get("session_factory")
    if not session_factory:
        logger.error("No session_factory found. Can't delete instructions.")
        await query.edit_message_text("Ошибка: нет подключения к БД.")
        return

    async with session_factory() as session:
        await set_user_instructions(session, chat_id, "")

    await query.answer("Инструкции удалены.")
    await instructions_menu(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Универсальный обработчик callback_data для тех случаев,
    которые не попадают в cabinet_callback_handler и т. д.
    """
    query = update.callback_query
    data = query.data

    await query.answer()

    if data == "back_to_menu":
        await menu_command(update, context)
        return

    elif data == "all_chats":
        await show_all_chats_list(update, context)
        return

    elif data == "favorite_chats":
        await show_favorite_chats_list(update, context)
        return

    elif data == "new_chat":
        return await new_chat_entry(update, context)

    elif data == "change_model":
        # Заранее заданный список моделей
        predefined_models = ["gpt-4o", "o1", "o3-mini"]
        keyboard = [[InlineKeyboardButton(model, callback_data=f"model_{model}")] for model in predefined_models]
        keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")])

        await query.edit_message_text(
            text="Выберите модель:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    elif data.startswith("model_"):
        session_factory = context.application.bot_data.get("session_factory")
        if not session_factory:
            logger.error("No session_factory found. Can't set model.")
            await query.edit_message_text("Ошибка: нет подключения к БД.")
            return

        selected_model = data.split("_", 1)[1]
        chat_id = query.message.chat.id

        async with session_factory() as session:
            await set_user_model(session, chat_id, selected_model)

        # Сразу возвращаем в меню (без "Выбрана модель: ...")
        await menu_command(update, context)
        return

    elif data == "update_instructions":
        return await instructions_menu(update, context)

    elif data == "instructions_add":
        return await instructions_add_entry(update, context)

    elif data == "instructions_edit":
        return await instructions_edit_entry(update, context)

    elif data == "instructions_delete":
        return await instructions_delete(update, context)

    elif data == "help":
        text = (
            "❓ Помощь:\n"
            "1. Отправьте любое текстовое сообщение – бот ответит.\n"
            "2. «Все чаты» – список всех ваших чатов.\n"
            "3. «Избранные чаты» – только ⭐.\n"
            "4. «Сменить модель» – переключение GPT-модели.\n"
            "5. «Инструкции» – задать/редактировать/удалить общие инструкции.\n"
            "6. «История» – просмотр истории активного чата.\n"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]
            ])
        )
        return

    elif data == "history_current_chat":
        session_factory = context.application.bot_data.get("session_factory")
        if not session_factory:
            logger.error("No session_factory found. Can't get active chat.")
            await query.edit_message_text("Ошибка: нет подключения к БД.")
            return

        user_id = query.message.chat.id
        async with session_factory() as session:
            active_id = await get_active_chat_id(session, user_id)
        if active_id:
            await show_chat_history(update, context, active_id, page=0)
        else:
            await query.edit_message_text(
                text="У вас нет активного чата. Создайте или выберите чат.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]
                ])
            )
        return

    elif data.startswith("open_chat_"):
        chat_db_id = int(data.split("_")[-1])
        await show_single_chat_menu(update, context, chat_db_id)
        return

    elif data.startswith("set_active_"):
        session_factory = context.application.bot_data.get("session_factory")
        if not session_factory:
            logger.error("No session_factory found. Can't set active chat.")
            await query.edit_message_text("Ошибка: нет подключения к БД.")
            return

        chat_db_id = int(data.split("_")[-1])
        user_id = query.message.chat.id
        async with session_factory() as session:
            await set_active_chat_id(session, user_id, chat_db_id)

        await query.edit_message_text(
            text=f"Чат {chat_db_id} теперь активен.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]
            ])
        )
        return

    elif data.startswith("rename_"):
        return await rename_chat_entry(update, context)

    elif data.startswith("delete_chat_"):
        session_factory = context.application.bot_data.get("session_factory")
        if not session_factory:
            logger.error("No session_factory found. Can't delete chat.")
            await query.edit_message_text("Ошибка: нет подключения к БД.")
            return

        chat_db_id = int(data.split("_")[-1])
        user_id = query.message.chat.id
        async with session_factory() as session:
            active_id = await get_active_chat_id(session, user_id)
            if active_id == chat_db_id:
                await set_active_chat_id(session, user_id, None)
            await delete_chat(session, chat_db_id)

        await query.edit_message_text(
            text=f"Чат {chat_db_id} удалён.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]
            ])
        )
        return

    elif data.startswith("fav_"):
        session_factory = context.application.bot_data.get("session_factory")
        if not session_factory:
            logger.error("No session_factory found. Can't favorite chat.")
            await query.edit_message_text("Ошибка: нет подключения к БД.")
            return
        chat_db_id = int(data.split("_")[-1])
        async with session_factory() as session:
            await set_chat_favorite(session, chat_db_id, True)

        await show_single_chat_menu(update, context, chat_db_id)
        return

    elif data.startswith("unfav_"):
        session_factory = context.application.bot_data.get("session_factory")
        if not session_factory:
            logger.error("No session_factory found. Can't unfavorite chat.")
            await query.edit_message_text("Ошибка: нет подключения к БД.")
            return
        chat_db_id = int(data.split("_")[-1])
        async with session_factory() as session:
            await set_chat_favorite(session, chat_db_id, False)

        await show_single_chat_menu(update, context, chat_db_id)
        return

    elif data.startswith("history_"):
        # history_<chat_id>:page_<N>
        parts = data.split(":")
        chat_part = parts[0].split("_")[-1]
        chat_db_id = int(chat_part)
        page = 0
        if len(parts) > 1 and parts[1].startswith("page_"):
            page = int(parts[1].split("_")[-1])
        await show_chat_history(update, context, chat_db_id, page)
        return

    # Если ничего не подошло
    await query.edit_message_text(
        "Неизвестная команда.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]
        ])
    )
    return ConversationHandler.END

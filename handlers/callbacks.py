# handlers/callbacks.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from db import (
    get_user_instructions,
    set_user_instructions,
    set_user_model,
    get_user_model,
    get_active_chat_id,
    set_active_chat_id,
    delete_chat,
    set_chat_favorite
)
from handlers.menu import menu_command
from handlers.chats import (
    show_all_chats_list,
    show_favorite_chats_list,
    show_single_chat_menu,
    show_chat_history
)
from handlers.conversation import (
    rename_chat_entry,
    new_chat_entry,
    receive_instructions,           # <-- Старый метод
    instructions_add_entry,         # <-- Новый метод
    instructions_edit_entry
)
from config import (
    SET_INSTRUCTIONS,
    SET_NEW_CHAT_TITLE,
    SET_RENAME_CHAT,
    AVAILABLE_MODELS
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------------
#  МИНИ-МЕНЮ ИНСТРУКЦИЙ
# --------------------------------------------------------------------------------
async def instructions_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает текущие инструкции, кнопки Добавить/Редактировать/Удалить
    """
    query = update.callback_query
    chat_id = query.message.chat.id

    current_instructions = get_user_instructions(chat_id) or ""
    is_empty = (not current_instructions.strip())

    if is_empty:
        text = "Текущие инструкции: (пусто)"
        keyboard = [[InlineKeyboardButton("Добавить инструкции", callback_data="instructions_add")]]
    else:
        text = f"Текущие инструкции:\n\n{current_instructions}"
        keyboard = [[InlineKeyboardButton("Редактировать инструкции", callback_data="instructions_edit"),
                     InlineKeyboardButton("Удалить", callback_data="instructions_delete")]]

    # Кнопка "В меню"
    keyboard.append([InlineKeyboardButton("В меню", callback_data="back_to_menu")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def instructions_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Удаляет инструкции (ставит "") и возвращается в меню инструкций
    """
    query = update.callback_query
    chat_id = query.message.chat.id

    set_user_instructions(chat_id, "")
    await query.answer("Инструкции удалены.")

    # Снова открываем меню инструкций
    await instructions_menu(update, context)


# --------------------------------------------------------------------------------
#  ГЛАВНЫЙ button_handler
# --------------------------------------------------------------------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        keyboard = [[InlineKeyboardButton(model, callback_data=f"model_{model}")] for model in AVAILABLE_MODELS]
        keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")])
        await query.edit_message_text("Выберите модель:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif data.startswith("model_"):
        selected_model = data.split("_", 1)[1]
        chat_id = query.message.chat.id
        set_user_model(chat_id, selected_model)
        await query.edit_message_text(
            text=f"Выбрана модель: {selected_model}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]])
        )
        return

    # --------------------------------
    # Блок «Меню инструкций»
    # --------------------------------
    elif data == "update_instructions":
        # Вместо старой логики - показываем меню инструкций
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
            "5. «Инструкции» – задать / редактировать / удалить общие инструкции.\n"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]])
        )
        return

    # --------------------------------
    # Управление чатами
    # --------------------------------
    elif data.startswith("open_chat_"):
        chat_db_id = int(data.split("_")[-1])
        await show_single_chat_menu(update, context, chat_db_id)
        return

    elif data.startswith("set_active_"):
        chat_db_id = int(data.split("_")[-1])
        user_id = query.message.chat.id
        set_active_chat_id(user_id, chat_db_id)
        await query.edit_message_text(
            text=f"Чат {chat_db_id} теперь активен.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]])
        )
        return

    elif data.startswith("rename_"):
        return await rename_chat_entry(update, context)

    elif data.startswith("delete_chat_"):
        chat_db_id = int(data.split("_")[-1])
        user_id = query.message.chat.id
        if get_active_chat_id(user_id) == chat_db_id:
            set_active_chat_id(user_id, None)
        delete_chat(chat_db_id)
        await query.edit_message_text(
            text=f"Чат {chat_db_id} удалён.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]])
        )
        return

    elif data.startswith("fav_"):
        chat_db_id = int(data.split("_")[-1])
        set_chat_favorite(chat_db_id, True)
        await show_single_chat_menu(update, context, chat_db_id)
        return

    elif data.startswith("unfav_"):
        chat_db_id = int(data.split("_")[-1])
        set_chat_favorite(chat_db_id, False)
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

    # --------------------------------
    # Если ничего не подошло
    # --------------------------------
    await query.edit_message_text(
        "Неизвестная команда.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]])
    )
    return ConversationHandler.END

# db.py
import sqlite3
from config import DB_PATH, DEFAULT_INSTRUCTIONS

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Таблица users
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            selected_model TEXT,
            instructions TEXT,
            active_chat_id INTEGER
        )
    ''')
    # Таблица чатов
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            is_favorite INTEGER DEFAULT 0
        )
    ''')
    # Таблица сообщений
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            role TEXT,
            content TEXT
        )
    ''')
    conn.commit()
    conn.close()

def upgrade_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Проверяем наличие столбца is_favorite в user_chats
    c.execute("PRAGMA table_info(user_chats)")
    columns = [row[1] for row in c.fetchall()]
    if "is_favorite" not in columns:
        c.execute("ALTER TABLE user_chats ADD COLUMN is_favorite INTEGER DEFAULT 0")
        conn.commit()

    # Проверяем instructions, active_chat_id в users
    c.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in c.fetchall()]
    if "instructions" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN instructions TEXT")
        conn.commit()
    if "active_chat_id" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN active_chat_id INTEGER")
        conn.commit()

    conn.close()

# ------------------- USERS -------------------
def get_user_model(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT selected_model FROM users WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_user_model(chat_id: int, model: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    existing = get_user_model(chat_id)
    if existing is None:
        c.execute(
            "INSERT INTO users (chat_id, selected_model, instructions, active_chat_id) VALUES (?, ?, ?, ?)",
            (chat_id, model, DEFAULT_INSTRUCTIONS, None)
        )
    else:
        c.execute("UPDATE users SET selected_model=? WHERE chat_id=?", (model, chat_id))
    conn.commit()
    conn.close()

def get_user_instructions(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT instructions FROM users WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else None

def set_user_instructions(chat_id: int, instructions: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if get_user_model(chat_id) is None:
        c.execute(
            "INSERT INTO users (chat_id, selected_model, instructions, active_chat_id) VALUES (?, ?, ?, ?)",
            (chat_id, "gpt-3.5-turbo", instructions, None)
        )
    else:
        c.execute("UPDATE users SET instructions=? WHERE chat_id=?", (instructions, chat_id))
    conn.commit()
    conn.close()

def get_active_chat_id(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT active_chat_id FROM users WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_active_chat_id(chat_id: int, active_chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET active_chat_id=? WHERE chat_id=?", (active_chat_id, chat_id))
    conn.commit()
    conn.close()

# ------------------- CHATS -------------------
def create_new_chat(chat_id: int, title: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    from db import get_user_model  # Можно импортировать сверху, если не вызывает круговую зависимость
    if get_user_model(chat_id) is None:
        c.execute(
            "INSERT INTO users (chat_id, selected_model, instructions, active_chat_id) VALUES (?, ?, ?, ?)",
            (chat_id, "gpt-3.5-turbo", DEFAULT_INSTRUCTIONS, None)
        )
        conn.commit()

    c.execute("INSERT INTO user_chats (user_id, title, is_favorite) VALUES (?, ?, 0)", (chat_id, title))
    new_chat_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_chat_id

def get_user_chats(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, is_favorite FROM user_chats WHERE user_id=?", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_favorite_chats(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, is_favorite FROM user_chats WHERE user_id=? AND is_favorite=1", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def delete_chat(chat_db_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM chat_messages WHERE chat_id=?", (chat_db_id,))
    c.execute("DELETE FROM user_chats WHERE id=?", (chat_db_id,))
    conn.commit()
    conn.close()

def rename_chat(chat_db_id: int, new_title: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE user_chats SET title=? WHERE id=?", (new_title, chat_db_id))
    conn.commit()
    conn.close()

def set_chat_favorite(chat_db_id: int, is_fav: bool):
    val = 1 if is_fav else 0
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE user_chats SET is_favorite=? WHERE id=?", (val, chat_db_id))
    conn.commit()
    conn.close()

def get_chat_title_by_id(chat_db_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT title FROM user_chats WHERE id=?", (chat_db_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# ------------------- MESSAGES -------------------
def add_message_to_chat(chat_db_id: int, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO chat_messages (chat_id, role, content) VALUES (?, ?, ?)", (chat_db_id, role, content))
    conn.commit()
    conn.close()

def get_chat_messages(chat_db_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content FROM chat_messages WHERE chat_id=? ORDER BY id ASC", (chat_db_id,))
    rows = c.fetchall()
    conn.close()
    messages = [{"role": row[0], "content": row[1]} for row in rows]
    return messages

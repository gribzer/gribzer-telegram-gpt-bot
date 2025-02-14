# app/telegram_bot/utils.py

import re
from app.config import MAX_TELEGRAM_TEXT, TRUNCATE_SUFFIX

def partial_escape_markdown_v2(text: str) -> str:
    """
    Экранирует специальные символы MarkdownV2 в тексте,
    кроме тех, что уже находятся в кодовых блоках (обрабатываются в convert_to_telegram_markdown_v2).
    """
    # Спецсимволы экранируем двойными обратными слэшами.
    # Обратите внимание на включённый бэктик (`) и обратные слэши (\\).
    special_chars = "\\[\\]\\(\\)~`>#\\+\\-=\\|{}\\.!"
    # При помощи re.escape() дополнительно экранируем спецсимволы для шаблона.
    pattern = f"([{re.escape(special_chars)}])"
    return re.sub(pattern, r'\\\1', text)

def convert_to_telegram_markdown_v2(text: str) -> str:
    """
    Разбивает текст на сегменты, чтобы отдельно обрабатывать кодовые блоки (```...``` или `...`).
    Вне кодовых блоков экранирует спецсимволы через partial_escape_markdown_v2.
    """
    # Шаблон ищет либо тройные бэктики (с любым содержимым),
    # либо одиночные бэктики вокруг слов/фраз.
    pattern = r"(```[\s\S]+?```|`[^`]+`)"
    segments = re.split(pattern, text)

    for i, segment in enumerate(segments):
        # Если сегмент НЕ начинается с ``` и НЕ является одинарным `...`,
        # то экранируем спецсимволы в этом сегменте
        if not (segment.startswith("```") or (segment.startswith("`") and segment.endswith("`"))):
            segments[i] = partial_escape_markdown_v2(segment)

    return "".join(segments)

def truncate_if_too_long(text: str, limit: int = MAX_TELEGRAM_TEXT) -> str:
    """
    Если текст превышает limit, обрезает его и добавляет TRUNCATE_SUFFIX.
    """
    if len(text) <= limit:
        return text
    else:
        # С учётом добавления TRUNCATE_SUFFIX
        return text[: limit - len(TRUNCATE_SUFFIX)] + TRUNCATE_SUFFIX

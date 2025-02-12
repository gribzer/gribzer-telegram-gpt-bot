# utils.py
import re
from config import MAX_TELEGRAM_TEXT, TRUNCATE_SUFFIX

def partial_escape_markdown_v2(text: str) -> str:
    special_chars = r'\[\]\(\)~`>#\+\-=|{}\.!'
    pattern = f'([{re.escape(special_chars)}])'
    return re.sub(pattern, r'\\\1', text)

def convert_to_telegram_markdown_v2(text: str) -> str:
    pattern = r"(```[\s\S]+?```|`[^`]+`)"
    segments = re.split(pattern, text)
    for i, segment in enumerate(segments):
        if not (segment.startswith("```") or (segment.startswith("`") and segment.endswith("`"))):
            segments[i] = partial_escape_markdown_v2(segment)
    return "".join(segments)

def truncate_if_too_long(text: str, limit: int = MAX_TELEGRAM_TEXT) -> str:
    if len(text) <= limit:
        return text
    else:
        return text[: limit - len(TRUNCATE_SUFFIX)] + TRUNCATE_SUFFIX

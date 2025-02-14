# proxyapi_client.py

import httpx
from config import PROXY_API_KEY, TIMEOUT

# Базовый URL к proxyapi (если у вас OpenAI-совместимые методы)
BASE_URL = "https://api.proxyapi.ru/openai/v1"

# Глобальный список моделей (заполняется при init_available_models())
AVAILABLE_MODELS = []

def _make_headers() -> dict:
    """Возвращает заголовки для запросов к proxyapi."""
    return {
        "Authorization": f"Bearer {PROXY_API_KEY}",
        "Content-Type": "application/json",
    }

def init_available_models():
    """
    Один раз вызывается при старте бота, чтобы заполнить AVAILABLE_MODELS.
    Если что-то пошло не так, список остаётся пустым.
    """
    global AVAILABLE_MODELS
    try:
        models = fetch_available_models()
        AVAILABLE_MODELS = models
        print(f"[INFO] Список доступных моделей: {AVAILABLE_MODELS}")
    except Exception as e:
        print(f"[ERROR] Не удалось получить список моделей: {e}")
        AVAILABLE_MODELS = []

def fetch_available_models() -> list:
    """
    Делает запрос к /v1/models и возвращает список идентификаторов (id) доступных моделей.
    """
    url = f"{BASE_URL}/models"
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.get(url, headers=_make_headers())
        resp.raise_for_status()
        data = resp.json()
        # Предположим, data = { "object": "list", "data": [ ... ] }
        models = [m["id"] for m in data.get("data", []) if "id" in m]
        return models


def create_chat_completion(
    model: str,
    messages: list,
    temperature: float = 1.0,
    max_tokens: int = 2048,
    top_p: float = 1.0,
    frequency_penalty: float = 0.0,
    presence_penalty: float = 0.0,
    # Доп. параметры, если нужно
) -> dict:
    """
    Запрос к /v1/chat/completions на proxyapi. 
    Возвращает JSON-ответ. Пример:
    {
      "id": "chatcmpl-1234",
      "object": "chat.completion",
      "choices": [...],
      ...
    }
    """
    url = f"{BASE_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty
    }

    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(url, headers=_make_headers(), json=payload)
        resp.raise_for_status()
        return resp.json()


def create_embedding(model: str, input_data: str | list) -> dict:
    """
    Запрос к /v1/embeddings. Возвращает JSON, содержащий эмбеддинги.
    """
    url = f"{BASE_URL}/embeddings"
    payload = {
        "model": model,
        "input": input_data
    }
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(url, headers=_make_headers(), json=payload)
        resp.raise_for_status()
        return resp.json()


def upload_file(file_path: str, purpose: str = "fine-tune") -> dict:
    """
    Запрос к /v1/files (загрузка файла).
    """
    url = f"{BASE_URL}/files"
    with httpx.Client(timeout=TIMEOUT) as client:
        with open(file_path, "rb") as f:
            files = {"file": (file_path, f, "application/octet-stream")}
            data = {"purpose": purpose}
            resp = client.post(url, headers={"Authorization": f"Bearer {PROXY_API_KEY}"}, data=data, files=files)
            resp.raise_for_status()
            return resp.json()


def generate_image(prompt: str, n: int = 1, size: str = "1024x1024") -> dict:
    """
    Пример для генерации изображений /v1/images/generations.
    """
    # Если для /images/ нужен другой base URL, поправьте на нужный.
    url = f"{BASE_URL.rsplit('/chat', 1)[0]}/images/generations"
    payload = {
        "prompt": prompt,
        "n": n,
        "size": size
    }
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(url, headers=_make_headers(), json=payload)
        resp.raise_for_status()
        return resp.json()


def transcribe_audio(file_path: str, model: str = "whisper-1") -> dict:
    """
    Пример для расшифровки аудио (/v1/audio/transcriptions).
    """
    url = f"{BASE_URL}/audio/transcriptions"
    with httpx.Client(timeout=TIMEOUT) as client:
        with open(file_path, "rb") as f:
            files = {"file": (file_path, f, "audio/mpeg")}
            data = {"model": model}
            resp = client.post(url, headers={"Authorization": f"Bearer {PROXY_API_KEY}"}, data=data, files=files)
            resp.raise_for_status()
            return resp.json()

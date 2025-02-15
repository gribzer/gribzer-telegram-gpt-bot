import hashlib
import httpx

from app.config import (
    T_KASSA_TERMINAL,
    T_KASSA_PASSWORD,
    T_KASSA_SECRET_KEY,
    T_KASSA_IS_TEST,
    T_KASSA_API_URL,
)

class TKassaClient:
    """
    Логика T-Kassa/Tinkoff.
    init_payment -> /Init
    get_state -> /GetState
    """

    def __init__(self):
        self.terminal_key = T_KASSA_TERMINAL
        self.password = T_KASSA_PASSWORD
        self.secret_key = T_KASSA_SECRET_KEY
        self.api_url = T_KASSA_API_URL.rstrip("/")

    def _generate_token(self, payload: dict) -> str:
        """
        Если нужно MD5-токен (согласно документации Tinkoff).
        Чаще нужно взять поля (кроме Token, Receipt), 
        склеить их значения, + secret_key, взять md5.
        """
        exclude = ("Token", "Receipt")
        keys = sorted(k for k in payload if k not in exclude and payload[k] is not None)
        data_str = "".join(str(payload[k]) for k in keys)
        data_str += str(self.secret_key or "")
        return hashlib.md5(data_str.encode("utf-8")).hexdigest()

    async def init_payment(self, amount_coins: int, order_id: str, description: str, customer_key: str) -> dict:
        """
        Инициализировать платеж (метод /Init).
        amount_coins: сумма в копейках (100 руб => 10000)
        order_id: уникальный ID (строка)
        description: описание
        customer_key: идентификатор покупателя (напр. chat_id)
        """
        url = f"{self.api_url}/Init"
        payload = {
            "TerminalKey": self.terminal_key,
            "Password": self.password,  # частая практика указывать Password
            "Amount": amount_coins,
            "OrderId": order_id,
            "Description": description,
            "CustomerKey": customer_key,
        }

        # Если TestMode=1, прикладываем
        if T_KASSA_IS_TEST:
            # Некоторые системы ждут "Data": {"TestMode": "1"}
            # Или поле "TestMode": True. Зависит от реализации.
            # Допустим, T-Kassa ждёт Data.TestMode
            payload["Data"] = {"TestMode": "1"}

        # Если нужен Token (MD5), раскомментировать
        # payload["Token"] = self._generate_token(payload)

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()

    async def get_state(self, payment_id: str) -> dict:
        """
        Проверить статус платежа (метод /GetState).
        """
        url = f"{self.api_url}/GetState"
        payload = {
            "TerminalKey": self.terminal_key,
            "Password": self.password,
            "PaymentId": payment_id,
        }
        # payload["Token"] = self._generate_token(payload)

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()

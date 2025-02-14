# app/services/tkassa_service.py

import hashlib
import httpx
from app.config import T_KASSA_TERMINAL_KEY, T_KASSA_SECRET_KEY, T_KASSA_API_URL

class TKassaClient:
    """
    Клиент для инициализации платежей и проверки статуса в Т-Кассе (Tinkoff).
    Адаптируйте поля payload и _generate_token под реальную схему API.
    """

    def __init__(self):
        self.terminal_key = T_KASSA_TERMINAL_KEY
        self.secret_key = T_KASSA_SECRET_KEY
        self.api_url = (T_KASSA_API_URL or "https://securepay.tinkoff.ru/v2").rstrip("/")

    def _generate_token(self, payload: dict) -> str:
        """
        Пример генерации токена (классическая схема Tinkoff):
        1. Убираем из payload поля 'Token' и 'Receipt'.
        2. Сортируем оставшиеся поля по ключам.
        3. Конкатенируем их значения (строковые).
        4. Добавляем в конец secretKey.
        5. Берём md5 от итоговой строки в hex.
        """
        exclude = ("Token", "Receipt")
        keys = sorted(k for k in payload if k not in exclude and payload[k] is not None)
        data_str = "".join(str(payload[k]) for k in keys)
        data_str += str(self.secret_key or "")
        return hashlib.md5(data_str.encode("utf-8")).hexdigest()

    async def init_payment(self, amount_coins: int, order_id: str, description: str, customer_key: str) -> dict:
        """
        Инициализировать платёж (метод /Init)
        :param amount_coins: сумма в копейках (например, 100 руб => 10000)
        :param order_id: уникальный идентификатор заказа (строка)
        :param description: описание платежа (строка)
        :param customer_key: идентификатор покупателя (например, chat_id)
        :return: dict-ответ от T-Kassa
        """
        url = f"{self.api_url}/Init"
        payload = {
            "TerminalKey": self.terminal_key,
            "Amount": amount_coins,
            "OrderId": order_id,
            "Description": description,
            "CustomerKey": customer_key,
        }
        payload["Token"] = self._generate_token(payload)

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def get_state(self, payment_id: str) -> dict:
        """
        Проверить статус платежа (метод /GetState)
        :param payment_id: PaymentId, полученный из /Init (resp["PaymentId"])
        :return: dict, содержащее статус ("Status" = 'AUTHORIZED', 'CONFIRMED', ...)
        """
        url = f"{self.api_url}/GetState"
        payload = {
            "TerminalKey": self.terminal_key,
            "PaymentId": payment_id,
        }
        payload["Token"] = self._generate_token(payload)

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()

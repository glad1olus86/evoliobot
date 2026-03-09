"""
HTTP-клиент для запросов к Make.com webhook.

Бот POST {klientTelefon} → Make.com ищет в Data store → JSON

Реальный формат ответа от Make.com (с Array aggregator):
  {"json": "{\"array\":[{\"data\":{\"idUkol\":...,\"idPripad\":...,...}},...],...}"}
  — двойной JSON: внешний {"json": "..."} + внутренний с массивом array[].data
"""

import json
import logging
import aiohttp
from config import MAKE_WEBHOOK_URL, MAKE_REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


def _parse_response(data) -> list[dict]:
    """
    Нормализует ответ Make.com в список словарей.

    Make.com может вернуть:
      - {"json": "{...}"}           → один кейс, data внутри строки
      - [{"json": "{...}"}, ...]    → несколько кейсов
      - {"json": "[{...}, ...]"}    → массив внутри строки
      - обычный dict/list           → напрямую
    """
    # Если массив — обрабатываем каждый элемент
    if isinstance(data, list):
        result = []
        for item in data:
            result.extend(_parse_response(item))
        return result

    if isinstance(data, dict):
        # Make.com заворачивает в {"json": "..."}
        if "json" in data and isinstance(data["json"], str):
            try:
                inner = json.loads(data["json"])
                return _parse_response(inner)
            except json.JSONDecodeError:
                logger.error("Failed to parse inner JSON: %s", data["json"][:200])
                return []

        # Array aggregator: {"array": [{"data": {...}}, ...], "__IMTAGGLENGTH__": N}
        if "array" in data and isinstance(data["array"], list):
            result = []
            for item in data["array"]:
                if isinstance(item, dict) and "data" in item:
                    result.append(item["data"])
                elif isinstance(item, dict):
                    result.append(item)
            return result

        # Обычный dict — это один кейс
        if data:
            return [data]

    return []


async def fetch_cases(phone: str, name: str) -> list[dict] | None:
    """
    Запрашивает кейсы через Make.com.

    Args:
        phone: телефон клиента (для поиска по klientTelefon в Data store)
        name:  "Имя Фамилия" (запасной вариант)
    """
    payload = {
        "klientTelefon": phone,
        "klientJmeno": name,
    }

    try:
        timeout = aiohttp.ClientTimeout(total=MAKE_REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                MAKE_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                logger.info("Make.com response: status=%s", resp.status)

                if resp.status != 200:
                    body = await resp.text()
                    logger.error("Make.com error: %s %s", resp.status, body)
                    return None

                data = await resp.json(content_type=None)
                logger.info("Make.com raw data: %s", str(data)[:500])

                cases = _parse_response(data)
                logger.info("Parsed %d case(s)", len(cases))
                return cases

    except aiohttp.ClientError as e:
        logger.error("Make.com request failed: %s", e)
        return None
    except Exception as e:
        logger.error("Unexpected error querying Make.com: %s", e)
        return None

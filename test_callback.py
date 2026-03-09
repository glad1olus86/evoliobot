"""
Тестовый скрипт для эмуляции callback от Evolio.

Использование:
    python test_callback.py <telegram_id>

Отправляет POST на http://localhost:8443/webhook/evolio
с фейковыми данными кейса, как будто это Evolio.
Это позволяет тестировать бота без реального подключения к Evolio.
"""

import sys
import requests

CALLBACK_URL = "http://localhost:8443/webhook/evolio"

# Пример реальных данных из Evolio (из спецификации)
SAMPLE_CASE = {
    "telegramId": None,  # будет подставлен из аргумента
    "idPripad": 538,
    "produkt": "AK",
    "cisloPripadu": "200/2024",
    "pripadDruh": "TREST",
    "stav": "AKTIVNI",
    "akVec": "Prchal Roman - TR - ex offo krádeže 10/24",
    "cisloJednaci": None,
    "sysZadal": 12,
    "sysZadano": "2024-10-19T09:19:55.053",
    "sysZadanoText": "19.10.2024 09:19:55.053",
    "akIdSubjektUctovatNa": None,
    "sysRowId": "ab37a1ad-a5a9-4ede-a581-d19a22cc0aca",
    "sysSourceId": None,
    "stavVyhledani": "Nalezen",
}


def main():
    if len(sys.argv) < 2:
        print("Использование: python test_callback.py <telegram_id>")
        print("Пример:        python test_callback.py 123456789")
        sys.exit(1)

    telegram_id = int(sys.argv[1])
    payload = {**SAMPLE_CASE, "telegramId": telegram_id}

    print(f"Отправляю callback на {CALLBACK_URL}")
    print(f"  telegramId: {telegram_id}")
    print(f"  idPripad:   {payload['idPripad']}")
    print(f"  akVec:      {payload['akVec']}")

    try:
        resp = requests.post(CALLBACK_URL, json=payload, timeout=5)
        print(f"\nОтвет: {resp.status_code} {resp.json()}")
    except requests.ConnectionError:
        print("\nОшибка: бот не запущен или порт 8443 недоступен.")
        print("Сначала запустите бот: python bot.py")
    except Exception as e:
        print(f"\nОшибка: {e}")


if __name__ == "__main__":
    main()

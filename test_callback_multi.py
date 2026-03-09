"""
Тестовый скрипт: отправляет несколько кейсов последовательно.

Использование:
    python test_callback_multi.py <telegram_id>

Полезно для тестирования если в будущем будет IdKlienti и множество кейсов.
"""

import sys
import requests

CALLBACK_URL = "http://localhost:8443/webhook/evolio"

SAMPLE_CASES = [
    {
        "idPripad": 538,
        "produkt": "AK",
        "cisloPripadu": "200/2024",
        "pripadDruh": "TREST",
        "stav": "AKTIVNI",
        "akVec": "Prchal Roman - TR - ex offo krádeže 10/24",
        "cisloJednaci": None,
        "sysZadanoText": "19.10.2024 09:19:55.053",
        "stavVyhledani": "Nalezen",
    },
    {
        "idPripad": 612,
        "produkt": "AK",
        "cisloPripadu": "45/2025",
        "pripadDruh": "CIVIL",
        "stav": "AKTIVNI",
        "akVec": "Novák Jan - občanskoprávní spor o nájem",
        "cisloJednaci": "12 C 45/2025",
        "sysZadanoText": "15.01.2025 14:30:00.000",
        "stavVyhledani": "Nalezen",
    },
    {
        "idPripad": 299,
        "produkt": "AK",
        "cisloPripadu": "88/2023",
        "pripadDruh": "RODINNE",
        "stav": "UZAVREN",
        "akVec": "Svobodová Marie - rozvod a vypořádání SJM",
        "cisloJednaci": "7 C 88/2023",
        "sysZadanoText": "03.05.2023 10:00:00.000",
        "stavVyhledani": "Nalezen",
    },
]


def main():
    if len(sys.argv) < 2:
        print("Использование: python test_callback_multi.py <telegram_id>")
        sys.exit(1)

    telegram_id = int(sys.argv[1])

    for i, case in enumerate(SAMPLE_CASES):
        payload = {**case, "telegramId": telegram_id}
        print(f"[{i+1}/{len(SAMPLE_CASES)}] Отправляю кейс №{case['cisloPripadu']}...")

        try:
            resp = requests.post(CALLBACK_URL, json=payload, timeout=5)
            print(f"  -> {resp.status_code} {resp.json()}")
        except Exception as e:
            print(f"  -> Ошибка: {e}")


if __name__ == "__main__":
    main()

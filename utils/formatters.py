"""
Форматирование данных кейсов Evolio для отображения в Telegram.

Реальные поля из Data store "Aktivity Evolio":
  idPripad, idUkol, predmet, poznamka, stav, termin,
  pripadNazev, klientJmeno, klientTelefon, klientEmail
"""

import re

STAV_MAP = {
    "AKTIVNI": "🟢 Активный",
    "Aktivní": "🟢 Активный",
    "UZAVREN": "🔴 Закрыт",
    "Uzavřen": "🔴 Закрыт",
    "PRERUSENI": "🟡 Приостановлен",
    "Přerušen": "🟡 Приостановлен",
    "ARCHIV": "⚫ Архив",
}


def _strip_html(text: str) -> str:
    """Убирает HTML-теги из текста."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    return clean.strip()


def _get(case: dict, *keys, default="—") -> str:
    """Ищет значение по нескольким возможным именам полей."""
    for key in keys:
        val = case.get(key)
        if val is not None and str(val).strip() != "":
            return str(val).strip()
    return default


def format_stav(stav: str) -> str:
    if not stav or stav == "—":
        return "❓ Статус неизвестен"
    return STAV_MAP.get(stav, f"📌 {stav}")


def format_case_card(case: dict) -> str:
    """Полная карточка кейса."""
    nazev = _get(case, "pripadNazev", "predmet")
    id_pripad = _get(case, "idPripad")
    stav = format_stav(_get(case, "stav", default=""))
    poznamka = _strip_html(_get(case, "poznamka", default=""))
    termin = _get(case, "termin")
    klient = _get(case, "klientJmeno")
    email = _get(case, "klientEmail")
    telefon = _get(case, "klientTelefon")

    lines = [
        f"📋 <b>{nazev}</b>",
        f"━━━━━━━━━━━━━━━━━━━━━",
        f"🆔 ID дела: {id_pripad}",
        f"{stav}",
        f"👤 Клиент: {klient}",
    ]

    if telefon != "—":
        lines.append(f"📞 Телефон: {telefon}")
    if email != "—":
        lines.append(f"📧 Email: {email}")
    if termin != "—":
        lines.append(f"📅 Срок: {termin}")
    if poznamka and poznamka != "—":
        # Обрезаем длинные заметки
        if len(poznamka) > 300:
            poznamka = poznamka[:297] + "..."
        lines.append(f"📝 Заметка: {poznamka}")

    lines.append(f"━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def format_case_button_text(case: dict) -> str:
    """Короткий текст для inline-кнопки в списке кейсов."""
    nazev = _get(case, "pripadNazev", "predmet", default="Без названия")
    stav = _get(case, "stav", default="")

    # Добавляем эмодзи статуса если есть
    if stav and stav != "—":
        emoji = format_stav(stav).split(" ", 1)[0]
        label = f"{emoji} {nazev}"
    else:
        label = nazev

    # Telegram ограничивает callback_data в 64 байта,
    # а текст кнопки — визуально ~55 символов нормально
    if len(label) > 55:
        label = label[:52] + "..."
    return label

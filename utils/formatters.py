"""
Formátování dat případů Evolio pro zobrazení v Telegramu.

Pole z Data store "Aktivity Evolio":
  idPripad, idUkol, predmet, poznamka, stav, termin,
  pripadNazev, klientJmeno, klientTelefon, klientEmail
"""

import re


def _strip_html(text: str) -> str:
    """Odstraní HTML tagy z textu."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    return clean.strip()


def _html_to_telegram(text: str) -> str:
    """Převede HTML z Evolio na Telegram HTML formát.

    <p>...</p> → text + newline
    <b>, <i>, <u> — ponechá (Telegram je podporuje)
    Ostatní tagy odstraní.
    """
    if not text:
        return ""
    # <br> / <br/> → newline
    result = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    # </p> → newline
    result = re.sub(r"</p>", "\n", result, flags=re.IGNORECASE)
    # <p...> → nic
    result = re.sub(r"<p[^>]*>", "", result, flags=re.IGNORECASE)
    # Povolené Telegram tagy: b, i, u, s, code, pre
    allowed = r"</?(?:b|i|u|s|code|pre)>"
    # Odstraní ostatní tagy
    result = re.sub(r"<(?!/?(?:b|i|u|s|code|pre)[ >/])[^>]+>", "", result)
    return result.strip()


def _get(case: dict, *keys, default="—") -> str:
    """Hledá hodnotu podle několika možných názvů polí."""
    for key in keys:
        val = case.get(key)
        if val is not None and str(val).strip() != "":
            return str(val).strip()
    return default


def _format_date(raw: str) -> str:
    """Extrahuje datum YYYY-MM-DD z ISO řetězce jako 2026-03-09T08:00:00."""
    if not raw or raw == "—":
        return "—"
    return raw[:10]


def format_case_card(items: list[dict]) -> str:
    """Karta případu (seskupeno podle idPripad).

    items — seznam všech záznamů se stejným idPripad,
    seřazených podle idUkol sestupně (nejnovější první).
    """
    first = items[0]
    nazev = _get(first, "pripadNazev")
    id_pripad = _get(first, "idPripad")

    # Poslední aktualizace — predmet + poznamka z záznamu s nejvyšším idUkol
    predmet = _get(first, "predmet", default="")
    poznamka = _html_to_telegram(_get(first, "poznamka", default=""))
    if len(poznamka) > 300:
        poznamka = poznamka[:297] + "..."

    lines = [
        f"📋 <b>{nazev}</b>",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"🆔 ID případu: {id_pripad}",
        "📝 Poslední aktualizace:",
    ]

    if predmet and predmet != "—":
        lines.append(f"\n<b>{predmet}</b>")
    if poznamka and poznamka != "—":
        lines.append(f"\n{poznamka}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def format_case_archive(items: list[dict]) -> str:
    """Archiv — seznam všech záznamů pro jeden případ.

    items seřazeny podle idUkol sestupně.
    """
    first = items[0]
    nazev = _get(first, "pripadNazev")
    id_pripad = _get(first, "idPripad")

    lines = [
        f"📜 <b>Archiv: {nazev}</b>",
        f"🆔 ID případu: {id_pripad}",
        "━━━━━━━━━━━━━━━━━━━━━",
    ]

    for item in items:
        termin = _format_date(_get(item, "termin", default=""))
        predmet = _get(item, "predmet", default="")
        poznamka = _html_to_telegram(_get(item, "poznamka", default=""))

        if not poznamka:
            poznamka = predmet if predmet and predmet != "—" else "—"

        if len(poznamka) > 200:
            poznamka = poznamka[:197] + "..."

        # Заголовок: дата + predmet (жирный)
        header_parts = []
        if termin and termin != "—":
            header_parts.append(f"📅 {termin}")
        if predmet and predmet != "—":
            header_parts.append(f"<b>{predmet}</b>")

        if header_parts:
            lines.append(" — ".join(header_parts))
        lines.append(poznamka)
        lines.append("")  # пустая строка между записями

    lines.append("━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def format_case_button_text(items: list[dict]) -> str:
    """Krátký text pro inline tlačítko v seznamu případů."""
    first = items[0]
    nazev = _get(first, "pripadNazev", "predmet", default="Bez názvu")

    if len(nazev) > 55:
        nazev = nazev[:52] + "..."
    return nazev

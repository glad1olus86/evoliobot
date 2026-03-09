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
    nazev = _get(first, "pripadNazev", "predmet")
    id_pripad = _get(first, "idPripad")

    # Poslední aktualizace — predmet z záznamu s nejvyšším idUkol
    latest_predmet = _strip_html(_get(first, "predmet", default=""))
    if not latest_predmet:
        latest_predmet = _strip_html(_get(first, "poznamka", default="—"))
    if len(latest_predmet) > 200:
        latest_predmet = latest_predmet[:197] + "..."

    lines = [
        f"📋 <b>{nazev}</b>",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"🆔 ID případu: {id_pripad}",
        f"📝 Poslední aktualizace: {latest_predmet}",
        "━━━━━━━━━━━━━━━━━━━━━",
    ]

    return "\n".join(lines)


def format_case_archive(items: list[dict]) -> str:
    """Archiv — seznam všech záznamů pro jeden případ.

    items seřazeny podle idUkol sestupně.
    """
    first = items[0]
    nazev = _get(first, "pripadNazev", "predmet")
    id_pripad = _get(first, "idPripad")

    lines = [
        f"📋 <b>{nazev}</b>",
        f"🆔 ID případu: {id_pripad}",
        "━━━━━━━━━━━━━━━━━━━━━",
    ]

    for item in items:
        termin = _format_date(_get(item, "termin", default=""))
        poznamka = _strip_html(_get(item, "poznamka", default=""))
        if not poznamka:
            poznamka = _strip_html(_get(item, "predmet", default="—"))
        if len(poznamka) > 150:
            poznamka = poznamka[:147] + "..."

        if termin and termin != "—":
            lines.append(f"📅 {termin} — {poznamka}")
        else:
            lines.append(f"📄 {poznamka}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def format_case_button_text(items: list[dict]) -> str:
    """Krátký text pro inline tlačítko v seznamu případů."""
    first = items[0]
    nazev = _get(first, "pripadNazev", "predmet", default="Bez názvu")

    if len(nazev) > 55:
        nazev = nazev[:52] + "..."
    return nazev

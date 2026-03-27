"""
Formátování dat případů Evolio pro zobrazení v Telegramu.

Pole z Data store "Aktivity Evolio":
  idPripad, idUkol, predmet, poznamka, stav, termin,
  pripadNazev, klientJmeno, klientTelefon, klientEmail
"""

import re

CALENDAR_BASE_URL = "https://calendar.app.google/5uMEKH4TLEKK2kLd7"


def _calendar_link(handler_name: str | None = None) -> str:
    """Vrátí odkaz na kalendář, volitelně personalizovaný."""
    url = CALENDAR_BASE_URL
    if handler_name:
        anchor = handler_name.replace(" ", "")
        url = f"{url}#{anchor}"
    label = f"Sjednat schůzku s {handler_name}" if handler_name else "Sjednat si schůzku"
    return f'📅 <a href="{url}">{label}</a>'


def _find_in_items(items: list[dict], *keys) -> str:
    """Hledá první neprázdnou hodnotu v seznamu záznamů."""
    for item in items:
        for key in keys:
            val = item.get(key)
            if val is not None and str(val).strip():
                return str(val).strip()
    return ""


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
    """Převede ISO datum 2026-03-09T08:00:00 na DD.MM.YYYY."""
    if not raw or raw == "—":
        return "—"
    date_part = raw[:10]
    parts = date_part.split("-")
    if len(parts) == 3:
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return date_part


def format_case_card(items: list[dict], latest_docs: list[dict] | None = None) -> str:
    """Karta případu (seskupeno podle idPripad).

    items — seznam všech záznamů se stejným idPripad,
    seřazených podle idUkol sestupně (nejnovější první).
    latest_docs — volitelný seznam posledních dokumentů z DB.
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

    # Kdo vyřizuje případ (hledá ve všech záznamech — starší mohou mít NULL)
    vyrizuje = _find_in_items(items, "vyrizujeJmeno")
    if vyrizuje:
        lines.append(f"\n👨‍💼 <b>Vyřizuje:</b> {vyrizuje}")

    if latest_docs:
        lines.append("\n📎 <b>Dokumenty:</b>")
        for doc in latest_docs[:5]:
            date_raw = doc.get("created_at", "")[:10] if doc.get("created_at") else ""
            date_str = _format_date(date_raw)
            lines.append(f"  📎 {doc['filename']} ({date_str})")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📞 (+420) 732 394 849")
    lines.append("✉️ info@modernipravnik.cz")
    lines.append("🕐 Po–Pá 9:00–18:00")
    lines.append("")
    lines.append(_calendar_link(vyrizuje if vyrizuje else None))

    return "\n".join(lines)


def format_case_archive(items: list[dict], documents: list[dict] | None = None) -> str:
    """Archiv — seznam všech záznamů pro jeden případ.

    items seřazeny podle idUkol sestupně.
    documents — volitelný seznam dokumentů z DB.
    """
    first = items[0]
    nazev = _get(first, "pripadNazev")
    id_pripad = _get(first, "idPripad")

    # Группировка документов по дате
    docs_by_date: dict[str, list[dict]] = {}
    if documents:
        for doc in documents:
            doc_date = doc.get("created_at", "")[:10] if doc.get("created_at") else ""
            docs_by_date.setdefault(doc_date, []).append(doc)

    vyrizuje = _find_in_items(items, "vyrizujeJmeno")

    lines = [
        f"📜 <b>Archiv: {nazev}</b>",
        f"🆔 ID případu: {id_pripad}",
    ]
    if vyrizuje:
        lines.append(f"👨‍💼 Vyřizuje: {vyrizuje}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")

    shown_raw_dates = set()
    for item in items:
        termin_raw = _get(item, "termin", default="")[:10]
        termin = _format_date(termin_raw)
        predmet = _get(item, "predmet", default="")
        poznamka = _html_to_telegram(_get(item, "poznamka", default=""))

        if not poznamka:
            poznamka = predmet if predmet and predmet != "—" else "—"

        if len(poznamka) > 200:
            poznamka = poznamka[:197] + "..."

        header_parts = []
        if termin and termin != "—":
            header_parts.append(f"📅 {termin}")
            shown_raw_dates.add(termin_raw)
        if predmet and predmet != "—":
            header_parts.append(f"<b>{predmet}</b>")

        if header_parts:
            lines.append(" — ".join(header_parts))
        lines.append(poznamka)

        # Документы привязанные к этой дате
        if termin_raw and termin_raw != "—" and termin_raw in docs_by_date:
            for doc in docs_by_date[termin_raw]:
                lines.append(f"  📎 {doc['filename']}")

        lines.append("")

    # Документы без привязки к дате обновления
    for doc_date, docs in docs_by_date.items():
        if doc_date and doc_date not in shown_raw_dates:
            lines.append(f"📅 {_format_date(doc_date)}")
            for doc in docs:
                lines.append(f"  📎 {doc['filename']}")
            lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    if vyrizuje:
        lines.append(f"👨‍💼 <b>Vyřizuje:</b> {vyrizuje}")
    lines.append("📞 (+420) 732 394 849")
    lines.append("✉️ info@modernipravnik.cz")
    lines.append("🕐 Po–Pá 9:00–18:00")
    lines.append("")
    lines.append(_calendar_link(vyrizuje if vyrizuje else None))

    return "\n".join(lines)


def format_case_button_text(items: list[dict]) -> str:
    """Krátký text pro inline tlačítko v seznamu případů."""
    first = items[0]
    nazev = _get(first, "pripadNazev", "predmet", default="Bez názvu")

    if len(nazev) > 55:
        nazev = nazev[:52] + "..."
    return nazev

"""
Formátování dat případů Evolio pro zobrazení v Telegramu.

Pole z Data store "Aktivity Evolio":
  idPripad, idUkol, predmet, poznamka, stav, termin,
  pripadNazev, klientJmeno, klientTelefon, klientEmail
"""

import re

STAV_MAP = {
    "AKTIVNI": "🟢 Aktivní",
    "Aktivní": "🟢 Aktivní",
    "UZAVREN": "🔴 Uzavřen",
    "Uzavřen": "🔴 Uzavřen",
    "PRERUSENI": "🟡 Pozastaven",
    "Přerušen": "🟡 Pozastaven",
    "ARCHIV": "⚫ Archiv",
}


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


def format_stav(stav: str) -> str:
    if not stav or stav == "—":
        return "❓ Stav neznámý"
    return STAV_MAP.get(stav, f"📌 {stav}")


def format_case_card(case: dict) -> str:
    """Úplná karta případu."""
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
        f"🆔 ID případu: {id_pripad}",
        f"{stav}",
        f"👤 Klient: {klient}",
    ]

    if telefon != "—":
        lines.append(f"📞 Telefon: {telefon}")
    if email != "—":
        lines.append(f"📧 E-mail: {email}")
    if termin != "—":
        lines.append(f"📅 Termín: {termin}")
    if poznamka and poznamka != "—":
        if len(poznamka) > 300:
            poznamka = poznamka[:297] + "..."
        lines.append(f"📝 Poznámka: {poznamka}")

    lines.append(f"━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def format_case_button_text(case: dict) -> str:
    """Krátký text pro inline tlačítko v seznamu případů."""
    nazev = _get(case, "pripadNazev", "predmet", default="Bez názvu")
    stav = _get(case, "stav", default="")

    if stav and stav != "—":
        emoji = format_stav(stav).split(" ", 1)[0]
        label = f"{emoji} {nazev}"
    else:
        label = nazev

    if len(label) > 55:
        label = label[:52] + "..."
    return label

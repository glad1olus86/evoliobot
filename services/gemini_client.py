"""
Klient pro Google Gemini 2.5 Flash API.

Používá se pro AI chat asistenta advokátní kanceláře Moderní Právník.
"""

import json
import logging

import google.generativeai as genai

from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Jsi AI asistent advokátní kanceláře Moderní Právník.

JAZYK:
- Odpovídej VŽDY a CELOU odpovědí v jazyce, ve kterém klient napsal POSLEDNÍ zprávu.
- Pokud klient píše rusky — odpovídej celou odpověď RUSKY.
- Pokud klient píše česky — odpovídej celou odpověď ČESKY.
- NIKDY nemíchej jazyky v jedné odpovědi. Data případů PŘEKLÁDEJ do jazyka klienta.

STYL:
- NEPOZDRAVUJ. Klient už byl pozdraven systémem. Žádné "Dobrý den", "Zdravím", "Привет" atd.
- Piš přímo k věci.
- Buď stručný, ale informativní.
- Používej odstavce pro oddělení témat.

DATA PŘÍPADŮ:
Dostáváš POUZE názvy případů a předměty záznamů (bez detailů, bez osobních údajů). \
To je záměrné — slouží to k ochraně soukromí klienta.

PRAVIDLA PRO PŘÍPADY:

1. Když klient žádá o podrobnosti/detaily případu — \
vlož do odpovědi tag {{DETAIL:ID}} kde ID je číslo případu (idPripad). \
Například: {{DETAIL:896}}. Systém automaticky nahradí tag kompletními daty.

2. Před tagem {{DETAIL:ID}} můžeš napsat krátký úvod (1-2 věty) v jazyce klienta. \
Například: "Zde jsou podrobnosti k Vašemu případu:" a pak {{DETAIL:896}}.

3. Můžeš zmínit NÁZVY záznamů (předměty), které vidíš v datech. \
Například: "Evidujeme záznamy: Stav řízení u soudu, Platba zálohy apod."

4. ⛔ NIKDY NEVYMÝŠLEJ obsah záznamů, poznámky, termíny ani částky. \
Nemáš k dispozici detaily — máš jen názvy. Detail vloží systém přes tag.

5. Pokud je více případů, můžeš vložit více tagů: {{DETAIL:896}} {{DETAIL:897}} atd.

6. Tag MUSÍ být na SAMOSTATNÉM řádku.

ZÁKAZY:
- ⛔ NIKDY nevymýšlej informace o případech, termínech, stavech, částkách.
- ⛔ NIKDY neposkytuj konkrétní právní rady, posudky ani doporučení kroků.
- Můžeš poskytnout pouze OBECNÉ informace o právních postupech.

NEJISTOTA:
Pokud si NEJSI 100% JISTÝ odpovědí nebo otázka vyžaduje odborný právní posudek:
→ Doporuč kontaktovat kancelář (kontakt vložíš na konec odpovědi):
  📞 (+420) 732 394 849
  ✉️ info@modernipravnik.cz
  🕐 Po–Pá 9:00–18:00

Chybná právní informace může klientovi způsobit škodu. V pochybnostech VŽDY odkaž na kancelář.

O KANCELÁŘI (pro odpovědi na dotazy):
- Sídlo: Mánesova 1175/48, 129 00 Vinohrady, Praha
- Služby: občanské právo, trestní právo, nemovitosti, pracovní právo, \
obchodní právo, rodinné právo, e-commerce, investiční a daňové poradenství
- Tým: Mgr. Petr Uklein, Mgr. Jana Hůsková (Brno), \
Mgr. Barbora Janáčková, Mgr. David Imre
"""

# Konfigurace Gemini
genai.configure(api_key=GEMINI_API_KEY)

MAX_HISTORY = 20  # maximální počet zpráv v historii


def _build_contents(
    chat_history: list[dict],
    user_message: str,
    cases_context: str | None = None,
) -> list[dict]:
    """Sestaví pole contents pro Gemini API."""
    contents = []

    # Kontext případů — все данные, чтобы AI видел все записи
    if cases_context:
        contents.append({
            "role": "user",
            "parts": [
                "[SYSTÉMOVÁ DATA — pouze názvy případů a záznamů. "
                "Pro zobrazení detailů vlož {{DETAIL:ID}}.]\n\n"
                + cases_context
            ],
        })
        contents.append({
            "role": "model",
            "parts": [
                "Mám k dispozici přehled případů (pouze názvy). "
                "Pro detaily vložím tag {{DETAIL:ID}}."
            ],
        })

    # Historie konverzace
    for msg in chat_history[-MAX_HISTORY:]:
        contents.append({
            "role": msg["role"],
            "parts": [msg["text"]],
        })

    # Aktuální zpráva
    contents.append({
        "role": "user",
        "parts": [user_message],
    })

    return contents


async def ask_gemini(
    user_message: str,
    chat_history: list[dict] | None = None,
    cases_context: str | None = None,
) -> str:
    """Odešle zprávu do Gemini a vrátí odpověď."""
    if not chat_history:
        chat_history = []

    try:
        model = genai.GenerativeModel(
            model_name="gemini-3.1-flash-lite-preview",
            system_instruction=SYSTEM_PROMPT,
        )

        contents = _build_contents(chat_history, user_message, cases_context)

        response = await model.generate_content_async(contents)

        return response.text

    except Exception as e:
        logger.error("Gemini API error: %s", e)
        return (
            "Omlouvám se, momentálně nemohu odpovědět. "
            "Zkuste to prosím později, nebo kontaktujte naši kancelář:\n"
            "📞 (+420) 732 394 849\n"
            "✉️ info@modernipravnik.cz"
        )

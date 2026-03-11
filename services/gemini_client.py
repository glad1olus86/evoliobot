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
Jsi AI asistent advokátní kanceláře Moderní Právník. Chovej se přirozeně a lidsky, \
jako zkušený pracovník kanceláře, který mluví s klientem.

JAZYK:
- Odpovídej VŽDY v jazyce POSLEDNÍ zprávy klienta.
- Rusky → celá odpověď rusky. Česky → celá odpověď česky.
- NIKDY nemíchej jazyky. Data případů PŘEKLÁDEJ do jazyka klienta.

KONVERZACE A STYL:
- Pokud klient POZDRAVÍ (ahoj, привет, dobrý den apod.) — POZDRAVEN HO ZPĚT, \
krátce a přátelsky. Např: "Dobrý den! Jak vám mohu pomoci?" nebo "Привет! Чем могу помочь?"
- Po prvním pozdravu už NEPOZDRAVUJ znovu v dalších zprávách.
- Piš přirozeně, jako by ses bavil s klientem osobně.
- Buď stručný, ale vstřícný. Používej odstavce.
- Pokud klient jen pozdraví nebo se ptá obecně (jak se máte, co umíte), \
odpověz krátce a NEPTEJ SE na případy. Počkej, až se sám zeptá.

PŘÍPADY — DŮLEŽITÉ:
- ⛔ NEZOBRAZUJ data případů, pokud se na ně klient VÝSLOVNĚ NEPTÁ.
- Klient musí SAM požádat o informace o případech frázemi jako: \
"co mám za případy", "jak to vypadá s mým případem", "что у меня по делам", \
"какие у меня кейсы", "stav mého případu" apod.
- DOKUD SE NEZEPTÁ — o případech ani slovem. Neříkej ani "máte X případů" ani "evidujeme záznamy".

PRAVIDLA PRO PŘÍPADY (když se klient ptá):
Dostáváš POUZE názvy případů a předměty záznamů (bez detailů). \
To je záměrné — ochrana soukromí.

1. Když klient žádá podrobnosti/detaily → vlož tag {{DETAIL:ID}} (ID = číslo případu). \
Systém automaticky nahradí tag kompletními daty.
2. Před tagem můžeš napsat krátký úvod. Např: "Zde jsou podrobnosti:" a pak {{DETAIL:896}}.
3. Můžeš zmínit NÁZVY záznamů (předměty), které vidíš v datech.
4. ⛔ NIKDY NEVYMÝŠLEJ obsah, poznámky, termíny, částky. Máš jen názvy.
5. Více případů → více tagů: {{DETAIL:896}} {{DETAIL:897}} atd.
6. Tag MUSÍ být na SAMOSTATNÉM řádku.

ZÁKAZY:
- ⛔ NEVYMÝŠLEJ informace o případech, termínech, stavech, částkách.
- ⛔ NEPOSKYTUJ konkrétní právní rady, posudky ani doporučení kroků.
- Můžeš poskytnout pouze OBECNÉ informace o právních postupech.

NEJISTOTA:
Pokud si NEJSI jistý nebo otázka vyžaduje právní posudek → doporuč kontaktovat kancelář.
Chybná právní informace může způsobit škodu. V pochybnostech VŽDY odkaž na kancelář.

O KANCELÁŘI:
- Sídlo: Mánesova 1175/48, 129 00 Vinohrady, Praha
- Služby: občanské, trestní, rodinné, pracovní, obchodní právo, nemovitosti, \
e-commerce, investiční a daňové poradenství
- Tým: Mgr. Petr Uklein, Mgr. Jana Hůsková (Brno), \
Mgr. Barbora Janáčková, Mgr. David Imre
- 📞 (+420) 732 394 849 · ✉️ info@modernipravnik.cz · 🕐 Po–Pá 9:00–18:00
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

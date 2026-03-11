"""
AI Chat handler — režim konverzace s Gemini 2.5 Flash.

V tomto režimu se zprávy uživatele NESMAŽOU a bot odpovídá
novými zprávami (ne editací). /menu vrací do single-message UI.
"""

import json
import logging
import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, LinkPreviewOptions
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext

from handlers.states import ChatMode
from handlers.ui import delete_user_msg, send_ui, MAIN_MENU_KB, MAIN_MENU_TEXT
from db.crud import get_user
from services.make_client import fetch_cases
from services.gemini_client import ask_gemini
from utils.auth import check_blocked, record_attempt, remaining_attempts, verify_password, is_session_valid, refresh_session
from utils.formatters import format_case_archive

router = Router()
logger = logging.getLogger(__name__)

CONTACT_BLOCK = (
    "\n\n━━━━━━━━━━━━━━━━━━━━━\n"
    "📞 (+420) 732 394 849\n"
    "✉️ info@modernipravnik.cz\n"
    "🕐 Po–Pá 9:00–18:00\n\n"
    '📅 <a href="https://calendar.app.google/5uMEKH4TLEKK2kLd7">Sjednat si schůzku</a>'
)

# Триггеры — если ответ содержит данные кейсов или упоминает канцелярию
_CONTACT_TRIGGERS = re.compile(
    r"kancel|kontakt|obrat.{0,5}se|spojte se|zavolej|napište nám|"
    r"doporuč.{0,10}kontakt|navštiv|obraťte|svažte|"
    # русские триггеры
    r"канцеляр|контакт|обрати.{0,5}с[яь]|свяжитесь|позвони|напишите|"
    # кейс-триггеры (когда AI выводит данные случаев)
    r"termín|TermIn|Termín|срок|případu|případům|přip[aá]d|"
    r"дел[оау]|случа[йю]|кейс",
    re.IGNORECASE,
)


def _md_to_html(text: str) -> str:
    """Převede Markdown z Gemini na Telegram HTML."""
    # **bold** → <b>bold</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # *italic* → <i>italic</i>
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    # `code` → <code>code</code>
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    # ### heading → <b>heading</b>
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    # • пункт с абзацем перед каждым (кроме первого подряд)
    # Сначала конвертируем маркеры
    text = re.sub(r"^\s*[\*\-]\s+", "• ", text, flags=re.MULTILINE)
    # Добавить пустую строку перед каждым •, если перед ним нет пустой строки
    text = re.sub(r"(?<!\n)\n(• )", r"\n\n\1", text)
    return text


def _expand_details(text: str, cases_grouped: dict) -> str:
    """Nahradí tagy {{DETAIL:ID}} kompletními daty případu."""
    def _replacer(match):
        pid = match.group(1)
        items = cases_grouped.get(pid)
        if not items:
            return f"(Případ ID:{pid} nenalezen)"
        return format_case_archive(items)

    return re.sub(r"\{\{DETAIL:(\d+)\}\}", _replacer, text)


def _postprocess(text: str) -> str:
    """Постобработка: контакты, финальная чистка."""
    html = _md_to_html(text)

    if _CONTACT_TRIGGERS.search(html):
        # Убрать контакты, которые Gemini мог вставить сам
        if "732 394 849" in html:
            html = re.sub(
                r"\n*[📞☎️]*\s*\(?\+?420\)?\s*732\s*394\s*849.*$",
                "",
                html,
                flags=re.DOTALL,
            )
        # Убрать разделители, которые Gemini мог вставить (━, ---, ___ и т.п.)
        html = re.sub(r"\n*[━─—\-_]{3,}\s*$", "", html)
        html = html.rstrip() + CONTACT_BLOCK

    return html


CHAT_GREETING = (
    "💬 <b>AI Asistent — Moderní Právník</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━\n"
    "Dobrý den! Jsem AI asistent advokátní kanceláře.\n"
    "Položte mi otázku — pokusím se Vám pomoci.\n\n"
    "Pro návrat do menu použijte příkaz /menu."
)


def _strip_html_simple(text: str) -> str:
    """Odstraní HTML tagy."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def _cases_to_context(cases_grouped: dict) -> str | None:
    """Převede data případů na ohlav (jen názvy, bez osobních dat) pro Gemini."""
    if not cases_grouped:
        return None

    lines = ["PŘÍPADY KLIENTA:"]
    for pid, items in cases_grouped.items():
        case_name = items[0].get("pripadNazev", f"Případ {pid}")
        lines.append(f'\nPŘÍPAD ID:{pid} — "{case_name}"')
        lines.append(f"  Počet záznamů: {len(items)}")
        lines.append("  Záznamy:")
        for item in items:
            predmet = item.get("predmet", "Bez předmětu")
            lines.append(f'  - "{predmet}"')

    return "\n".join(lines)


# ─── Kliknutí na tlačítko "AI Asistent" ───

@router.callback_query(F.data == "menu:chat")
async def start_chat(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Nejste registrován/a.", show_alert=True)
        return

    remaining = check_blocked(callback.from_user.id)
    if remaining:
        minutes = int(remaining // 60) + 1
        await callback.answer(
            f"Přístup zablokován. Zkuste to za {minutes} min.",
            show_alert=True,
        )
        return

    if await is_session_valid(callback.from_user.id):
        await callback.answer()
        await _enter_chat(callback.message, state, callback.from_user.id)
        return

    await callback.message.edit_text(
        "🔐 <b>Přístup k AI Asistentovi</b>\n\n"
        "Zadejte heslo:",
    )
    await state.set_state(ChatMode.waiting_password)
    await callback.answer()


# ─── Ověření hesla pro chat ───

@router.message(ChatMode.waiting_password)
async def chat_check_password(message: Message, state: FSMContext):
    await delete_user_msg(message)

    remaining = check_blocked(message.from_user.id)
    if remaining:
        minutes = int(remaining // 60) + 1
        await edit_ui(
            message, state,
            f"🔒 Přístup zablokován na {minutes} min.\n\n{MAIN_MENU_TEXT}",
            MAIN_MENU_KB,
        )
        await state.set_state(None)
        return

    entered = message.text.strip()
    user = await get_user(message.from_user.id)
    if not verify_password(entered, user["password_hash"]):
        record_attempt(message.from_user.id, success=False)

        remaining = check_blocked(message.from_user.id)
        if remaining:
            await edit_ui(
                message, state,
                "❌ Nesprávné heslo. Překročen počet pokusů.\n"
                "🔒 Přístup zablokován na 10 minut.\n\n" + MAIN_MENU_TEXT,
                MAIN_MENU_KB,
            )
            await state.set_state(None)
        else:
            left = remaining_attempts(message.from_user.id)
            await edit_ui(
                message, state,
                f"❌ Nesprávné heslo. Zbývající pokusy: {left}\n\n"
                "Zadejte heslo:",
            )
        return

    record_attempt(message.from_user.id, success=True)
    await refresh_session(message.from_user.id)

    await _enter_chat(message, state, message.from_user.id)


# ─── Вход в чат-режим ───

async def _enter_chat(message: Message, state: FSMContext, telegram_id: int):
    """Přepne do chat režimu: smaže menu zprávu, načte případy, odešle pozdrav."""
    # Smazat single-message UI
    data = await state.get_data()
    bot_msg_id = data.get("bot_msg_id")
    if bot_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, bot_msg_id)
        except Exception:
            pass
        await state.update_data(bot_msg_id=None)

    # Načíst případy pro kontext AI
    user = await get_user(telegram_id)
    phone = user["phone"]
    name = f"{user['first_name']} {user['last_name']}"

    cases_list = await fetch_cases(phone=phone, name=name)

    cases_grouped = {}
    if cases_list:
        from handlers.cases import _group_by_pripad
        cases_grouped = _group_by_pripad(cases_list)

    await state.update_data(
        cases=cases_grouped,
        cases_context=_cases_to_context(cases_grouped),
        chat_history=[],
        chat_msg_ids=[],
    )

    # Pozdrav
    greeting = await message.answer(CHAT_GREETING)
    await state.update_data(chat_msg_ids=[greeting.message_id])
    await state.set_state(ChatMode.chatting)


# ─── /menu — выход из чата в single-message UI ───

@router.message(ChatMode.chatting, Command("menu"))
async def cmd_menu_from_chat(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_msg_ids = data.get("chat_msg_ids", [])

    # Удалить ВСЕ сообщения чата + команду /menu
    all_ids = chat_msg_ids + [message.message_id]
    for msg_id in all_ids:
        try:
            await message.bot.delete_message(message.chat.id, msg_id)
        except Exception:
            pass

    await state.clear()
    await send_ui(message, state, MAIN_MENU_TEXT, MAIN_MENU_KB)


# ─── Обработка сообщений в чате ───

@router.message(ChatMode.chatting)
async def handle_chat_message(message: Message, state: FSMContext):
    if not message.text:
        return

    user_text = message.text.strip()

    # Typing indikátor
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    # Získat kontext a historii
    data = await state.get_data()
    chat_history = data.get("chat_history", [])
    cases_context = data.get("cases_context")

    # Volání Gemini
    logger.info("Asking Gemini: %s", user_text[:100])
    response = await ask_gemini(
        user_message=user_text,
        chat_history=chat_history,
        cases_context=cases_context,
    )
    logger.info("Gemini response (%d chars): %s", len(response), response[:200])

    # Aktualizovat historii
    chat_history.append({"role": "user", "text": user_text})
    chat_history.append({"role": "model", "text": response})

    # Omezit délku historie
    if len(chat_history) > 40:
        chat_history = chat_history[-40:]

    # Трекать message_id пользователя
    chat_msg_ids = data.get("chat_msg_ids", [])
    chat_msg_ids.append(message.message_id)

    await state.update_data(chat_history=chat_history)

    # Подставить детали кейсов вместо {{DETAIL:ID}}
    cases_grouped = data.get("cases", {})
    expanded = _expand_details(response, cases_grouped)

    # Převést Markdown → Telegram HTML + kontakty
    html_response = _postprocess(expanded)

    # Zkrátit pokud přesahuje limit Telegramu (4096 znaků)
    if len(html_response) > 4000:
        html_response = html_response[:4000] + "..."

    try:
        bot_reply = await message.answer(
            html_response,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception as e:
        logger.error("Telegram send error: %s\nResponse text: %s", e, html_response[:500])
        # Отправить без HTML как fallback
        plain = _strip_html_simple(html_response)
        if len(plain) > 4000:
            plain = plain[:4000] + "..."
        bot_reply = await message.answer(plain)

    # Трекать message_id бота
    chat_msg_ids.append(bot_reply.message_id)
    await state.update_data(chat_msg_ids=chat_msg_ids)

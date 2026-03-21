import logging
import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery, Message, InlineKeyboardMarkup,
    InlineKeyboardButton, LinkPreviewOptions,
)
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext

from db.crud import get_user
from handlers.states import ChatMode
from handlers.ui import MAIN_MENU_KB, MAIN_MENU_TEXT, send_ui, repost_ui, delete_user_msg, cleanup_quick_ai, ensure_bot_msg
from services.gemini_client import ask_gemini

router = Router()
logger = logging.getLogger(__name__)

# Минимум для "осмысленного" сообщения
_MIN_MEANINGFUL_LEN = 3

# Рандомный мусор: только цифры, или только 1-2 буквы без смысла, спецсимволы
_JUNK_PATTERN = re.compile(r"^[\d\s\W]+$|^[a-zA-Zа-яА-ЯёЁ]{1,2}$")


def _is_meaningful(text: str) -> bool:
    """Zda zpráva vypadá jako skutečná otázka/žádost (ne náhodný znak)."""
    text = text.strip()
    if not text:
        return False
    # Мусор: цифры, спецсимволы, или 1-2 случайные буквы
    if _JUNK_PATTERN.match(text):
        return False
    # Всё остальное (слово 3+ букв, фраза) — осмысленное
    return True


# ─── Профиль ───

@router.callback_query(F.data == "menu:profile")
async def show_profile(callback: CallbackQuery, state: FSMContext):
    await ensure_bot_msg(callback, state)
    await cleanup_quick_ai(callback, state)
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Nejste registrován/a.", show_alert=True)
        return

    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Hlavní menu", callback_data="menu:main")]
    ])

    await repost_ui(
        callback, state,
        f"👤 <b>Váš profil</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Jméno: {user['first_name']}\n"
        f"Příjmení: {user['last_name']}\n"
        f"Telefon: {user['phone']}\n"
        f"Datum registrace: {user['created_at']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━",
        back_kb,
    )
    await callback.answer()


# ─── Nápověda ───

@router.callback_query(F.data == "menu:help")
async def show_help(callback: CallbackQuery, state: FSMContext):
    await ensure_bot_msg(callback, state)
    await cleanup_quick_ai(callback, state)
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Hlavní menu", callback_data="menu:main")]
    ])

    await repost_ui(
        callback, state,
        "ℹ️ <b>Nápověda</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Tento bot umožňuje prohlížet\n"
        "vaše soudní případy a komunikovat\n"
        "s AI asistentem.\n\n"
        "💬 <b>AI Asistent</b> — AI chat\n"
        "📂 <b>Případy</b> — seznam vašich věcí\n"
        "👤 <b>Profil</b> — váš účet\n\n"
        "Příkaz /menu — návrat do menu\n"
        "━━━━━━━━━━━━━━━━━━━━━",
        back_kb,
    )
    await callback.answer()


# ─── Zpět do menu ───

@router.callback_query(F.data == "menu:main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await ensure_bot_msg(callback, state)
    await cleanup_quick_ai(callback, state)
    data = await state.get_data()
    bot_msg_id = data.get("bot_msg_id")
    await state.clear()
    if bot_msg_id:
        await state.update_data(bot_msg_id=bot_msg_id)

    await repost_ui(callback, state, MAIN_MENU_TEXT, MAIN_MENU_KB)
    await callback.answer()


# ─── /menu — возврат из любого режима ───

@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await _reset_to_menu(message, state)


# ─── Fallback: любое сообщение без стейта ───

@router.message()
async def fallback_any_message(message: Message, state: FSMContext):
    """Ловит ВСЕ сообщения, не обработанные другими хендлерами."""
    if not message.text:
        await delete_user_msg(message)
        return

    text = message.text.strip()
    user = await get_user(message.from_user.id)

    # Не зарегистрирован — на регистрацию
    if not user or not user["is_registered"]:
        await delete_user_msg(message)
        await send_ui(
            message, state,
            "👋 Nejprve se prosím zaregistrujte příkazem /start.",
        )
        return

    # Осмысленное сообщение → быстрый AI ответ с историей
    if _is_meaningful(text):
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

        from handlers.chat import _postprocess, _expand_details, _cases_to_context
        from handlers.cases import _group_by_pripad
        from services.make_client import fetch_cases

        data = await state.get_data()
        quick_history = data.get("quick_history", [])

        # Загрузить кейсы при первом сообщении (или использовать кеш)
        cases_grouped = data.get("quick_cases")
        cases_context = data.get("quick_cases_context")
        if cases_grouped is None:
            cases_list = await fetch_cases(
                phone=user["phone"],
                name=f"{user['first_name']} {user['last_name']}",
            )
            if cases_list:
                cases_grouped = _group_by_pripad(cases_list)
            else:
                cases_grouped = {}
            cases_context = _cases_to_context(cases_grouped)

        response = await ask_gemini(
            user_message=text,
            chat_history=quick_history,
            cases_context=cases_context,
        )

        # Раскрыть {{DETAIL:ID}} теги
        expanded = _expand_details(response, cases_grouped)
        html_response = _postprocess(expanded)

        if len(html_response) > 4000:
            html_response = html_response[:4000] + "..."

        # Обновить историю
        quick_history.append({"role": "user", "text": text})
        quick_history.append({"role": "model", "text": response})
        if len(quick_history) > 20:
            quick_history = quick_history[-20:]

        try:
            reply = await message.answer(
                html_response,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except Exception:
            from handlers.chat import _strip_html_simple
            plain = _strip_html_simple(html_response)
            reply = await message.answer(plain[:4000])

        # Трекать сообщения юзера + бота для удаления при навигации
        quick_ai_ids = data.get("quick_ai_ids", [])
        quick_ai_ids.append(message.message_id)
        quick_ai_ids.append(reply.message_id)
        await state.update_data(
            quick_ai_ids=quick_ai_ids,
            quick_history=quick_history,
            quick_cases=cases_grouped,
            quick_cases_context=cases_context,
        )
        return

    # Бессмысленное (1-2 символа) → просто показать меню
    await _reset_to_menu(message, state)


async def _reset_to_menu(message: Message, state: FSMContext):
    """Удаляет сообщение юзера, чистит старые сообщения, показывает меню."""
    await delete_user_msg(message)

    data = await state.get_data()
    bot_msg_id = data.get("bot_msg_id")
    chat_msg_ids = data.get("chat_msg_ids", [])
    quick_ai_ids = data.get("quick_ai_ids", [])

    for msg_id in chat_msg_ids + quick_ai_ids:
        try:
            await message.bot.delete_message(message.chat.id, msg_id)
        except Exception:
            pass

    await state.clear()
    # Вернуть bot_msg_id чтобы send_ui мог удалить старое меню
    if bot_msg_id:
        await state.update_data(bot_msg_id=bot_msg_id)

    user = await get_user(message.from_user.id)
    if user and user["is_registered"]:
        await send_ui(
            message, state,
            MAIN_MENU_TEXT,
            MAIN_MENU_KB,
        )
    else:
        await send_ui(
            message, state,
            "👋 Nejprve se prosím zaregistrujte příkazem /start.",
        )

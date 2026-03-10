import logging

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext

from handlers.states import CasesAccess
from handlers.ui import delete_user_msg, edit_ui, MAIN_MENU_KB, MAIN_MENU_TEXT
from db.crud import get_user
from services.make_client import fetch_cases
from utils.formatters import format_case_card, format_case_button_text, format_case_archive
from utils.auth import check_blocked, record_attempt, remaining_attempts, verify_password

router = Router()
logger = logging.getLogger(__name__)


def _group_by_pripad(cases_list: list[dict]) -> dict[str, list[dict]]:
    """Seskupí záznamy podle idPripad, seřadí podle idUkol sestupně."""
    groups: dict[str, list[dict]] = {}
    for case in cases_list:
        pid = str(case.get("idPripad", "unknown"))
        groups.setdefault(pid, []).append(case)
    for pid in groups:
        groups[pid].sort(key=lambda x: int(x.get("idUkol", 0)), reverse=True)
    return groups


def _cases_list_kb(cases_grouped: dict[str, list[dict]]) -> InlineKeyboardMarkup:
    buttons = []
    for case_id, items in cases_grouped.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"⚖️ {format_case_button_text(items)}",
                callback_data=f"case:{case_id}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Hlavní menu", callback_data="menu:main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── Tlačítko "Zobrazit případy" ───

@router.callback_query(F.data == "menu:cases")
async def request_password(callback: CallbackQuery, state: FSMContext):
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

    # Pokud už heslo bylo ověřeno — přeskočíme
    data = await state.get_data()
    if data.get("password_verified"):
        await callback.answer()
        await _load_and_show_cases(callback.message, state, callback.from_user.id)
        return

    await callback.message.edit_text(
        "🔐 <b>Přístup k případům</b>\n\n"
        "Zadejte heslo:",
    )
    await state.set_state(CasesAccess.waiting_password)
    await callback.answer()


# ─── Zadání hesla (textová zpráva) ───

@router.message(CasesAccess.waiting_password)
async def check_password(message: Message, state: FSMContext):
    await delete_user_msg(message)

    remaining = check_blocked(message.from_user.id)
    if remaining:
        minutes = int(remaining // 60) + 1
        await edit_ui(
            message, state,
            f"🔒 Přístup zablokován na {minutes} min.\n\n{MAIN_MENU_TEXT}",
            MAIN_MENU_KB,
        )
        await state.clear()
        return

    entered = message.text.strip()
    user = await get_user(message.from_user.id)
    is_correct = verify_password(entered, user["password_hash"])

    if not is_correct:
        record_attempt(message.from_user.id, success=False)

        remaining = check_blocked(message.from_user.id)
        if remaining:
            await edit_ui(
                message, state,
                "❌ Nesprávné heslo. Překročen počet pokusů.\n"
                f"🔒 Přístup zablokován na 10 minut.\n\n{MAIN_MENU_TEXT}",
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
    await state.update_data(password_verified=True)
    await state.set_state(None)

    await _load_and_show_cases(message, state, message.from_user.id)


async def _load_and_show_cases(message: Message, state: FSMContext, telegram_id: int):
    """Načte případy z Make.com a zobrazí seznam."""
    await edit_ui(message, state, "⏳ Načítám vaše případy...")

    user = await get_user(telegram_id)
    phone = user["phone"]
    name = f"{user['first_name']} {user['last_name']}"

    cases_list = await fetch_cases(phone=phone, name=name)

    if cases_list is None:
        await edit_ui(
            message, state,
            "⚠️ Služba případů je dočasně nedostupná.\nZkuste to prosím později.\n\n" + MAIN_MENU_TEXT,
            MAIN_MENU_KB,
        )
        return

    if not cases_list:
        await edit_ui(
            message, state,
            "📭 K vašemu profilu nebyly nalezeny žádné případy.\n\n" + MAIN_MENU_TEXT,
            MAIN_MENU_KB,
        )
        return

    cases_grouped = _group_by_pripad(cases_list)

    await state.update_data(cases=cases_grouped)
    await edit_ui(
        message, state,
        "📂 <b>Vaše případy:</b>",
        _cases_list_kb(cases_grouped),
    )


# ─── Karta případu ───

@router.callback_query(F.data.startswith("case:"))
async def show_case_detail(callback: CallbackQuery, state: FSMContext):
    case_id = callback.data.split(":", 1)[1]
    data = await state.get_data()
    cases = data.get("cases", {})

    items = cases.get(case_id)
    if not items:
        await callback.answer("Případ nenalezen.", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Archiv", callback_data=f"archive:{case_id}")],
        [InlineKeyboardButton(text="🔙 Zpět na případy", callback_data="back_to_cases")],
    ])

    await callback.message.edit_text(format_case_card(items), reply_markup=kb)
    await callback.answer()


# ─── Archiv případu ───

@router.callback_query(F.data.startswith("archive:"))
async def show_case_archive(callback: CallbackQuery, state: FSMContext):
    case_id = callback.data.split(":", 1)[1]
    data = await state.get_data()
    cases = data.get("cases", {})

    items = cases.get(case_id)
    if not items:
        await callback.answer("Případ nenalezen.", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Zpět na poslední", callback_data=f"case:{case_id}")],
        [InlineKeyboardButton(text="🔙 Zpět na případy", callback_data="back_to_cases")],
    ])

    await callback.message.edit_text(format_case_archive(items), reply_markup=kb)
    await callback.answer()


# ─── Navigace ───

@router.callback_query(F.data == "back_to_cases")
async def back_to_cases(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cases_grouped = data.get("cases", {})

    if not cases_grouped:
        await callback.answer("Seznam je zastaralý. Vyžádejte si případy znovu.", show_alert=True)
        return

    await callback.message.edit_text(
        "📂 <b>Vaše případy:</b>",
        reply_markup=_cases_list_kb(cases_grouped),
    )
    await callback.answer()

import hmac
import time
import logging

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext

from handlers.states import CasesAccess
from handlers.ui import delete_user_msg, edit_ui, MAIN_MENU_KB, MAIN_MENU_TEXT
from db.crud import get_user
from services.make_client import fetch_cases
from utils.formatters import format_case_card, format_case_button_text
from config import CASES_PASSWORD, MAX_PASSWORD_ATTEMPTS, PASSWORD_BLOCK_SECONDS

router = Router()
logger = logging.getLogger(__name__)

_password_attempts: dict[int, dict] = {}


def _check_blocked(telegram_id: int) -> float | None:
    info = _password_attempts.get(telegram_id)
    if not info:
        return None
    blocked_until = info.get("blocked_until", 0)
    remaining = blocked_until - time.time()
    return remaining if remaining > 0 else None


def _record_attempt(telegram_id: int, success: bool):
    if success:
        _password_attempts.pop(telegram_id, None)
        return
    info = _password_attempts.setdefault(telegram_id, {"attempts": 0, "blocked_until": 0})
    info["attempts"] += 1
    if info["attempts"] >= MAX_PASSWORD_ATTEMPTS:
        info["blocked_until"] = time.time() + PASSWORD_BLOCK_SECONDS
        info["attempts"] = 0


def _cases_list_kb(cases_dict: dict) -> InlineKeyboardMarkup:
    """Строит inline-клавиатуру списка кейсов."""
    buttons = []
    for case_id, case in cases_dict.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"⚖️ {format_case_button_text(case)}",
                callback_data=f"case:{case_id}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── Кнопка "Просмотреть кейсы" ───

@router.callback_query(F.data == "menu:cases")
async def request_password(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Вы не зарегистрированы.", show_alert=True)
        return

    remaining = _check_blocked(callback.from_user.id)
    if remaining:
        minutes = int(remaining // 60) + 1
        await callback.answer(
            f"Доступ заблокирован. Попробуйте через {minutes} мин.",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        "🔐 <b>Доступ к кейсам</b>\n\n"
        "Введите пароль:",
    )
    await state.set_state(CasesAccess.waiting_password)
    await callback.answer()


# ─── Ввод пароля (текстовое сообщение) ───

@router.message(CasesAccess.waiting_password)
async def check_password(message: Message, state: FSMContext):
    await delete_user_msg(message)

    remaining = _check_blocked(message.from_user.id)
    if remaining:
        minutes = int(remaining // 60) + 1
        await edit_ui(
            message, state,
            f"🔒 Доступ заблокирован на {minutes} мин.\n\n{MAIN_MENU_TEXT}",
            MAIN_MENU_KB,
        )
        await state.clear()
        data_new = await state.get_data()  # preserve bot_msg_id handled by edit_ui
        return

    entered = message.text.strip()
    is_correct = hmac.compare_digest(entered, CASES_PASSWORD)

    if not is_correct:
        _record_attempt(message.from_user.id, success=False)

        remaining = _check_blocked(message.from_user.id)
        if remaining:
            await edit_ui(
                message, state,
                "❌ Неверный пароль. Превышено количество попыток.\n"
                f"🔒 Доступ заблокирован на 10 минут.\n\n{MAIN_MENU_TEXT}",
                MAIN_MENU_KB,
            )
            await state.set_state(None)
        else:
            info = _password_attempts.get(message.from_user.id, {})
            left = MAX_PASSWORD_ATTEMPTS - info.get("attempts", 0)
            await edit_ui(
                message, state,
                f"❌ Неверный пароль. Осталось попыток: {left}\n\n"
                "Введите пароль:",
            )
        return

    _record_attempt(message.from_user.id, success=True)

    # Пароль верный — загружаем кейсы
    await edit_ui(message, state, "⏳ Загружаю ваши кейсы...")

    user = await get_user(message.from_user.id)
    phone = user["phone"]
    name = f"{user['first_name']} {user['last_name']}"

    cases_list = await fetch_cases(phone=phone, name=name)

    await state.set_state(None)

    if cases_list is None:
        await edit_ui(
            message, state,
            "⚠️ Сервис кейсов временно недоступен.\nПопробуйте позже.\n\n" + MAIN_MENU_TEXT,
            MAIN_MENU_KB,
        )
        return

    if not cases_list:
        await edit_ui(
            message, state,
            "📭 По вашему профилю кейсы не найдены.\n\n" + MAIN_MENU_TEXT,
            MAIN_MENU_KB,
        )
        return

    cases_dict = {}
    for i, case in enumerate(cases_list):
        case_id = str(case.get("idPripad", case.get("idUkol", i)))
        cases_dict[case_id] = case

    await state.update_data(cases=cases_dict)
    await edit_ui(
        message, state,
        "📂 <b>Ваши кейсы:</b>",
        _cases_list_kb(cases_dict),
    )


# ─── Карточка кейса ───

@router.callback_query(F.data.startswith("case:"))
async def show_case_detail(callback: CallbackQuery, state: FSMContext):
    case_id = callback.data.split(":", 1)[1]
    data = await state.get_data()
    cases = data.get("cases", {})

    case = cases.get(case_id)
    if not case:
        await callback.answer("Кейс не найден.", show_alert=True)
        return

    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к кейсам", callback_data="back_to_cases")]
    ])

    await callback.message.edit_text(format_case_card(case), reply_markup=back_kb)
    await callback.answer()


# ─── Навигация ───

@router.callback_query(F.data == "back_to_cases")
async def back_to_cases(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cases_dict = data.get("cases", {})

    if not cases_dict:
        await callback.answer("Список устарел. Запросите кейсы заново.", show_alert=True)
        return

    await callback.message.edit_text(
        "📂 <b>Ваши кейсы:</b>",
        reply_markup=_cases_list_kb(cases_dict),
    )
    await callback.answer()

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from handlers.states import Registration
from handlers.ui import (
    delete_user_msg, send_ui, edit_ui,
    MAIN_MENU_KB, MAIN_MENU_TEXT,
)
from db.crud import get_user, create_user
from utils.validators import validate_name, validate_phone, normalize_phone

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await delete_user_msg(message)
    await state.clear()
    user = await get_user(message.from_user.id)

    if user and user["is_registered"]:
        await send_ui(
            message, state,
            f"Vítejte zpět, {user['first_name']}!\n\n{MAIN_MENU_TEXT}",
            MAIN_MENU_KB,
        )
    else:
        await send_ui(
            message, state,
            "👋 <b>Vítejte!</b>\n\n"
            "Pro zahájení práce je nutná registrace.\n\n"
            "✏️ Zadejte své <b>jméno</b>:",
        )
        await state.set_state(Registration.waiting_first_name)


@router.message(Registration.waiting_first_name)
async def process_first_name(message: Message, state: FSMContext):
    name = message.text.strip()
    await delete_user_msg(message)

    if not validate_name(name):
        await edit_ui(
            message, state,
            "⚠️ Jméno musí obsahovat pouze písmena (2–50 znaků).\n\n"
            "✏️ Zadejte své <b>jméno</b>:",
        )
        return

    await state.update_data(first_name=name)
    await edit_ui(
        message, state,
        f"✅ Jméno: <b>{name}</b>\n\n"
        "✏️ Zadejte své <b>příjmení</b>:",
    )
    await state.set_state(Registration.waiting_last_name)


@router.message(Registration.waiting_last_name)
async def process_last_name(message: Message, state: FSMContext):
    name = message.text.strip()
    await delete_user_msg(message)

    if not validate_name(name):
        await edit_ui(
            message, state,
            "⚠️ Příjmení musí obsahovat pouze písmena (2–50 znaků).\n\n"
            "✏️ Zadejte své <b>příjmení</b>:",
        )
        return

    data = await state.get_data()
    await state.update_data(last_name=name)
    await edit_ui(
        message, state,
        f"✅ Jméno: <b>{data['first_name']}</b>\n"
        f"✅ Příjmení: <b>{name}</b>\n\n"
        "✏️ Zadejte své <b>telefonní číslo</b>\n"
        "(například +420123456789):",
    )
    await state.set_state(Registration.waiting_phone)


@router.message(Registration.waiting_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    await delete_user_msg(message)

    if not validate_phone(phone):
        await edit_ui(
            message, state,
            "⚠️ Nesprávný formát. Zadejte číslo ve formátu +XXXXXXXXXXX (9–15 číslic).\n\n"
            "✏️ Zadejte své <b>telefonní číslo</b>:",
        )
        return

    data = await state.get_data()
    normalized = normalize_phone(phone)

    await create_user(
        telegram_id=message.from_user.id,
        first_name=data["first_name"],
        last_name=data["last_name"],
        phone=normalized,
    )

    # Uložíme bot_msg_id před clear
    old_data = await state.get_data()
    bot_msg_id = old_data.get("bot_msg_id")
    await state.clear()
    if bot_msg_id:
        await state.update_data(bot_msg_id=bot_msg_id)

    await edit_ui(
        message, state,
        f"🎉 <b>Registrace dokončena!</b>\n\n"
        f"Vítejte, {data['first_name']}!\n\n"
        f"{MAIN_MENU_TEXT}",
        MAIN_MENU_KB,
    )

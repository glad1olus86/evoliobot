from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.fsm.context import FSMContext

from handlers.states import Registration
from handlers.ui import (
    delete_user_msg, send_ui, edit_ui,
    MAIN_MENU_KB, MAIN_MENU_TEXT,
)
from db.crud import get_user, get_user_by_phone, create_user
from utils.validators import validate_name, normalize_phone
from utils.auth import hash_password, refresh_session

router = Router()

# ReplyKeyboard s tlačítkem "Sdílet kontakt"
CONTACT_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📱 Sdílet telefonní číslo", request_contact=True)]
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

MIN_PASSWORD_LENGTH = 4


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
            "✏️ Zadejte své <b>jméno a příjmení</b>\n"
            "(oddělené mezerou):",
        )
        await state.set_state(Registration.waiting_full_name)


@router.message(Registration.waiting_full_name)
async def process_full_name(message: Message, state: FSMContext):
    text = message.text.strip()
    await delete_user_msg(message)

    parts = text.split()
    if len(parts) < 2:
        await edit_ui(
            message, state,
            "⚠️ Zadejte <b>jméno i příjmení</b> oddělené mezerou.\n\n"
            "✏️ Například: <i>Jan Novák</i>",
        )
        return

    first_name = parts[0].capitalize()
    last_name = " ".join(parts[1:]).title()

    if not validate_name(first_name) or not all(
        validate_name(p) for p in parts[1:]
    ):
        await edit_ui(
            message, state,
            "⚠️ Jméno a příjmení musí obsahovat pouze písmena.\n\n"
            "✏️ Zadejte své <b>jméno a příjmení</b>:",
        )
        return

    await state.update_data(first_name=first_name, last_name=last_name)

    # Удалить inline UI и показать ReplyKeyboard для контакта
    data = await state.get_data()
    bot_msg_id = data.get("bot_msg_id")
    if bot_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, bot_msg_id)
        except Exception:
            pass
        await state.update_data(bot_msg_id=None)

    contact_msg = await message.answer(
        f"✅ Jméno: <b>{first_name}</b>\n"
        f"✅ Příjmení: <b>{last_name}</b>\n\n"
        "📱 Stiskněte tlačítko níže pro sdílení\n"
        "vašeho telefonního čísla:\n\n"
        "<i>Disclaimer: Nebojte se, Vaše data a sdělené telefonní číslo "
        "jsou s námi v bezpečí. Vaše telefonní číslo slouží jen k propojení "
        "se systémem moderniPravnik.cz a k tomu, abyste se jen Vy ke svým "
        "informacím bezpečně dostali.</i>",
        reply_markup=CONTACT_KB,
    )
    await state.update_data(contact_msg_id=contact_msg.message_id)
    await state.set_state(Registration.waiting_phone)


# ─── Приём контакта (кнопка "Поделиться") ───

@router.message(Registration.waiting_phone, F.contact)
async def process_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    normalized = normalize_phone(phone)

    await _after_phone(message, state, normalized)


# ─── Debug: !!!+420... как ручной ввод номера ───

@router.message(Registration.waiting_phone, F.text.startswith("!!!"))
async def process_debug_phone(message: Message, state: FSMContext):
    phone = message.text.strip()[3:]
    normalized = normalize_phone(phone)

    if not normalized or len(normalized) < 9:
        await message.delete()
        return

    await _after_phone(message, state, normalized)


# ─── Любой другой текст в waiting_phone ───

@router.message(Registration.waiting_phone)
async def process_phone_text(message: Message, state: FSMContext):
    await delete_user_msg(message)


# ─── После получения номера → создание пароля ───

async def _after_phone(message: Message, state: FSMContext, phone: str):
    await delete_user_msg(message)

    # Удалить сообщение с ReplyKeyboard
    data = await state.get_data()
    contact_msg_id = data.get("contact_msg_id")
    if contact_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, contact_msg_id)
        except Exception:
            pass

    # Убрать ReplyKeyboard
    remove_msg = await message.answer("⏳", reply_markup=ReplyKeyboardRemove())
    await remove_msg.delete()

    # Проверка: номер уже зарегистрирован?
    existing = await get_user_by_phone(phone)
    if existing:
        await send_ui(
            message, state,
            "⚠️ <b>Toto telefonní číslo je již registrováno.</b>\n\n"
            "Pokud jste majitelem tohoto čísla, kontaktujte\n"
            "kancelář pro pomoc.\n\n"
            "📞 (+420) 732 394 849\n"
            "✉️ info@modernipravnik.cz\n\n"
            "Pro novou registraci stiskněte /start",
        )
        await state.clear()
        return

    await state.update_data(phone=phone)

    await send_ui(
        message, state,
        f"✅ Jméno: <b>{data['first_name']}</b>\n"
        f"✅ Příjmení: <b>{data['last_name']}</b>\n"
        f"✅ Telefon: <b>{phone}</b>\n\n"
        "🔐 Nyní si vytvořte <b>osobní heslo</b>\n"
        f"(minimálně {MIN_PASSWORD_LENGTH} znaky).\n\n"
        "Toto heslo budete používat pro přístup\n"
        "k případům a AI asistentovi.",
    )
    await state.set_state(Registration.waiting_new_password)


# ─── Создание пароля ───

@router.message(Registration.waiting_new_password)
async def process_new_password(message: Message, state: FSMContext):
    password = message.text.strip()
    await delete_user_msg(message)

    if len(password) < MIN_PASSWORD_LENGTH:
        await edit_ui(
            message, state,
            f"⚠️ Heslo musí mít alespoň {MIN_PASSWORD_LENGTH} znaky.\n\n"
            "🔐 Zadejte heslo:",
        )
        return

    await state.update_data(new_password=password)
    await edit_ui(
        message, state,
        "🔐 Zopakujte heslo pro potvrzení:",
    )
    await state.set_state(Registration.waiting_confirm_password)


# ─── Подтверждение пароля ───

@router.message(Registration.waiting_confirm_password)
async def process_confirm_password(message: Message, state: FSMContext):
    confirm = message.text.strip()
    await delete_user_msg(message)

    data = await state.get_data()
    if confirm != data.get("new_password"):
        await edit_ui(
            message, state,
            "⚠️ Hesla se neshodují. Zkuste to znovu.\n\n"
            f"🔐 Zadejte nové heslo (min. {MIN_PASSWORD_LENGTH} znaky):",
        )
        await state.set_state(Registration.waiting_new_password)
        return

    # Всё ок — создаём пользователя
    pw_hash = hash_password(confirm)

    await create_user(
        telegram_id=message.from_user.id,
        first_name=data["first_name"],
        last_name=data["last_name"],
        phone=data["phone"],
        password_hash=pw_hash,
    )

    # Сразу активировать сессию на 3 дня
    await refresh_session(message.from_user.id)

    bot_msg_id = (await state.get_data()).get("bot_msg_id")
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

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from db.crud import get_user
from handlers.ui import MAIN_MENU_KB, MAIN_MENU_TEXT

router = Router()


@router.callback_query(F.data == "menu:profile")
async def show_profile(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Nejste registrován/a.", show_alert=True)
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Hlavní menu", callback_data="menu:main")]
    ])

    await callback.message.edit_text(
        f"👤 <b>Váš profil</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Jméno: {user['first_name']}\n"
        f"Příjmení: {user['last_name']}\n"
        f"Telefon: {user['phone']}\n"
        f"Datum registrace: {user['created_at']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=back_kb,
    )
    await callback.answer()


@router.callback_query(F.data == "menu:help")
async def show_help(callback: CallbackQuery, state: FSMContext):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Hlavní menu", callback_data="menu:main")]
    ])

    await callback.message.edit_text(
        "ℹ️ <b>Nápověda</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Tento bot umožňuje prohlížet\n"
        "vaše soudní případy.\n\n"
        "📂 <b>Případy</b> — seznam vašich věcí\n"
        "👤 <b>Profil</b> — váš účet\n\n"
        "S dotazy se obracejte\n"
        "na svého advokáta.\n"
        "━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=back_kb,
    )
    await callback.answer()


@router.callback_query(F.data == "menu:main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    bot_msg_id = data.get("bot_msg_id")
    await state.clear()
    if bot_msg_id:
        await state.update_data(bot_msg_id=bot_msg_id)

    await callback.message.edit_text(MAIN_MENU_TEXT, reply_markup=MAIN_MENU_KB)
    await callback.answer()

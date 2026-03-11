"""
Single-message UI helpers.

Bot pracuje přes JEDNU zprávu, která se neustále edituje.
ID této zprávy je uloženo ve FSM state jako "bot_msg_id".
Všechny zprávy uživatele se ihned po zpracování mažou.
"""

import logging
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)


# ─── Inline klávesnice hlavního menu ───

MAIN_MENU_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💬 AI Asistent", callback_data="menu:chat")],
    [InlineKeyboardButton(text="📂 Zobrazit případy", callback_data="menu:cases")],
    [InlineKeyboardButton(text="👤 Můj profil", callback_data="menu:profile")],
    [InlineKeyboardButton(text="ℹ️ Nápověda", callback_data="menu:help")],
])

MAIN_MENU_TEXT = "🏠 <b>Hlavní menu</b>\n\nVyberte akci:"


async def delete_user_msg(message: Message):
    """Smaže zprávu uživatele (tiše, bez chyb)."""
    try:
        await message.delete()
    except Exception:
        pass


async def send_ui(message: Message, state: FSMContext, text: str,
                  keyboard: InlineKeyboardMarkup | None = None):
    """
    Odešle novou UI zprávu a uloží její ID.
    Stará UI zpráva se smaže.
    """
    await _delete_old_ui(message, state)
    msg = await message.answer(text, reply_markup=keyboard)
    await state.update_data(bot_msg_id=msg.message_id)


async def edit_ui(message: Message, state: FSMContext, text: str,
                  keyboard: InlineKeyboardMarkup | None = None):
    """
    Edituje existující UI zprávu.
    Pokud se nepodaří (smazaná / příliš stará) — odešle novou.
    """
    data = await state.get_data()
    bot_msg_id = data.get("bot_msg_id")

    if bot_msg_id:
        try:
            await message.bot.edit_message_text(
                text=text,
                chat_id=message.chat.id,
                message_id=bot_msg_id,
                reply_markup=keyboard,
            )
            return
        except Exception:
            pass

    # Fallback — pošleme novou
    await send_ui(message, state, text, keyboard)


async def ensure_bot_msg(callback: CallbackQuery, state: FSMContext):
    """Восстанавливает bot_msg_id из callback (на случай рестарта бота)."""
    data = await state.get_data()
    if not data.get("bot_msg_id"):
        await state.update_data(bot_msg_id=callback.message.message_id)


async def cleanup_quick_ai(source: Message | CallbackQuery, state: FSMContext):
    """Smaže dočasné AI odpovědi + zprávy uživatele z quick-chatu."""
    data = await state.get_data()
    quick_ai_ids = data.get("quick_ai_ids", [])
    if not quick_ai_ids:
        return
    bot = source.bot if hasattr(source, "bot") else source.message.bot
    chat_id = source.chat.id if hasattr(source, "chat") else source.message.chat.id
    for msg_id in quick_ai_ids:
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception:
            pass
    await state.update_data(quick_ai_ids=[], quick_history=[])


async def _delete_old_ui(message: Message, state: FSMContext):
    """Smaže starou UI zprávu, pokud existuje."""
    data = await state.get_data()
    old_id = data.get("bot_msg_id")
    if old_id:
        try:
            await message.bot.delete_message(message.chat.id, old_id)
        except Exception:
            pass

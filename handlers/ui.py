"""
Single-message UI helpers.

Бот работает через ОДНО сообщение, которое постоянно редактируется.
ID этого сообщения хранится в FSM state как "bot_msg_id".
Все сообщения пользователя удаляются сразу после обработки.
"""

import logging
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)


# ─── Inline-клавиатура главного меню ───

MAIN_MENU_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📂 Просмотреть кейсы", callback_data="menu:cases")],
    [InlineKeyboardButton(text="👤 Мой профиль", callback_data="menu:profile")],
    [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu:help")],
])

MAIN_MENU_TEXT = "🏠 <b>Главное меню</b>\n\nВыберите действие:"


async def delete_user_msg(message: Message):
    """Удаляет сообщение пользователя (тихо, без ошибок)."""
    try:
        await message.delete()
    except Exception:
        pass


async def send_ui(message: Message, state: FSMContext, text: str,
                  keyboard: InlineKeyboardMarkup | None = None):
    """
    Отправляет новое UI-сообщение и сохраняет его ID.
    Старое UI-сообщение удаляется.
    """
    await _delete_old_ui(message, state)
    msg = await message.answer(text, reply_markup=keyboard)
    await state.update_data(bot_msg_id=msg.message_id)


async def edit_ui(message: Message, state: FSMContext, text: str,
                  keyboard: InlineKeyboardMarkup | None = None):
    """
    Редактирует существующее UI-сообщение.
    Если не удалось (удалено / слишком старое) — отправляет новое.
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

    # Fallback — шлём новое
    await send_ui(message, state, text, keyboard)


async def _delete_old_ui(message: Message, state: FSMContext):
    """Удаляет старое UI-сообщение если есть."""
    data = await state.get_data()
    old_id = data.get("bot_msg_id")
    if old_id:
        try:
            await message.bot.delete_message(message.chat.id, old_id)
        except Exception:
            pass

from aiogram.fsm.state import StatesGroup, State


class Registration(StatesGroup):
    waiting_first_name = State()
    waiting_last_name = State()
    waiting_phone = State()
    waiting_new_password = State()
    waiting_confirm_password = State()


class CasesAccess(StatesGroup):
    waiting_password = State()


class ChatMode(StatesGroup):
    waiting_password = State()
    chatting = State()

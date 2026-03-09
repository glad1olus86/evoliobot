from aiogram.fsm.state import StatesGroup, State


class Registration(StatesGroup):
    waiting_first_name = State()
    waiting_last_name = State()
    waiting_phone = State()


class CasesAccess(StatesGroup):
    waiting_password = State()

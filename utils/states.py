"""
وضعیت‌های FSM برای فرآیندهای چندمرحله‌ای
"""

from aiogram.fsm.state import State, StatesGroup


class BuyConfigFSM(StatesGroup):
    """فرآیند خرید کانفیگ"""
    waiting_config_name = State()    # انتظار برای نام دلخواه کانفیگ


class AdminChargeFSM(StatesGroup):
    """فرآیند شارژ/کسر کیف پول توسط ادمین"""
    waiting_user_id = State()
    waiting_amount = State()
    waiting_description = State()


class AdminAddTariffFSM(StatesGroup):
    """فرآیند افزودن بسته جدید"""
    waiting_name = State()
    waiting_data_gb = State()
    waiting_days = State()
    waiting_price = State()


class AdminInboundFSM(StatesGroup):
    """فرآیند تغییر Inbound فعال"""
    waiting_inbound_id = State()

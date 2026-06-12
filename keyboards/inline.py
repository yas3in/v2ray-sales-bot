from typing import List
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import Tariff, UserConfig


def main_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🛒 خرید سرویس",   callback_data="buy_config")
    b.button(text="📋 سرویس‌های من", callback_data="my_configs")
    b.button(text="💳 شارژ کیف پول", callback_data="charge_wallet")
    b.button(text="💰 موجودی",        callback_data="show_balance")
    b.adjust(1)
    return b.as_markup()


def tariffs_kb(tariffs: List[Tariff]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in tariffs:
        b.button(
            text=f"📦 {t.name}  |  {t.data_limit_gb:.0f}GB  {t.duration_days}روز  |  {t.price:,.0f}T",
            callback_data=f"tariff:{t.id}",
        )
    b.button(text="🔙 بازگشت", callback_data="main_menu")
    b.adjust(1)
    return b.as_markup()


def user_configs_kb(configs: List[UserConfig]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for cfg in configs:
        display = cfg.label or cfg.panel_email
        b.button(text=f"🔑 {display}", callback_data=f"config_info:{cfg.id}")
    b.button(text="🔙 بازگشت", callback_data="main_menu")
    b.adjust(1)
    return b.as_markup()


def admin_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💳 شارژ/کسر کیف پول",  callback_data="admin_charge")
    b.button(text="📦 مدیریت بسته‌ها",     callback_data="admin_tariffs")
    b.button(text="⚙️ تنظیم Inbound",      callback_data="admin_inbound")
    b.button(text="👥 مدیریت کاربران",     callback_data="admin_users")
    b.adjust(1)
    return b.as_markup()


def admin_tariffs_kb(tariffs: List[Tariff]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in tariffs:
        b.button(text=f"✏️ {t.name}", callback_data=f"edit_tariff:{t.id}")
        b.button(text="🗑",            callback_data=f"del_tariff:{t.id}")
    b.button(text="➕ بسته جدید", callback_data="add_tariff")
    b.button(text="🔙 بازگشت",   callback_data="admin_menu")
    b.adjust(2, 1, 1)
    return b.as_markup()


def admin_user_kb(uid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💳 شارژ/کسر",  callback_data=f"quick_charge:{uid}")
    b.button(text="🔨 Ban",        callback_data=f"ban_user:{uid}")
    b.button(text="✅ Unban",      callback_data=f"unban_user:{uid}")
    b.button(text="🔙 بازگشت",   callback_data="admin_menu")
    b.adjust(2, 1)
    return b.as_markup()


def back_to_main_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏠 منوی اصلی", callback_data="main_menu")
    return b.as_markup()


def back_to_admin_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔙 پنل ادمین", callback_data="admin_menu")
    return b.as_markup()

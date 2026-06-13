"""هندلرهای پنل ادمین"""

import logging

from aiogram import F, Router, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

import database.crud as crud
from config import settings
from keyboards.inline import admin_menu_kb, admin_tariffs_kb, back_to_main_kb, back_to_admin_kb

from services.xui_api import xui_client

logger = logging.getLogger(__name__)
router = Router(name="admin")


def is_admin(uid: int) -> bool:
    return uid in settings.ADMIN_IDS


# ── FSM States ────────────────────────────────

class AdminChargeFSM(StatesGroup):
    waiting_user_id     = State()
    waiting_amount      = State()
    waiting_description = State()

class AdminAddTariffFSM(StatesGroup):
    waiting_name      = State()
    waiting_data_gb   = State()
    waiting_days      = State()
    waiting_price     = State()

class AdminEditTariffFSM(StatesGroup):
    waiting_field = State()
    waiting_value = State()

class AdminInboundFSM(StatesGroup):
    waiting_inbound_id = State()

class AdminUserSearchFSM(StatesGroup):
    waiting_query = State()


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id): return
    await message.answer("🛠 <b>پنل مدیریت</b>", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True); return
    await query.message.edit_text("🛠 <b>پنل مدیریت</b>", reply_markup=admin_menu_kb())
    await query.answer()


@router.callback_query(F.data == "admin_charge")
async def cb_admin_charge(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True); return
    await state.set_state(AdminChargeFSM.waiting_user_id)
    await query.message.edit_text("💳 شناسه عددی کاربر را وارد کنید:")
    await query.answer()

@router.message(AdminChargeFSM.waiting_user_id)
async def fsm_charge_uid(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not is_admin(message.from_user.id): return
    if not message.text.strip().isdigit():
        await message.answer("⚠️ عدد صحیح وارد کنید."); return
    user = await crud.get_user(session, int(message.text.strip()))
    if not user:
        await message.answer("❌ کاربر یافت نشد."); return
    await state.update_data(target_user_id=user.id)
    await state.set_state(AdminChargeFSM.waiting_amount)
    await message.answer(
        f"👤 {user.full_name} | موجودی: {user.balance:,.0f} تومان\n\n"
        "مبلغ (مثبت=شارژ | منفی=کسر):"
    )

@router.message(AdminChargeFSM.waiting_amount)
async def fsm_charge_amount(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id): return
    try:
        amount = float(message.text.strip().replace(",", ""))
    except ValueError:
        await message.answer("⚠️ مبلغ نامعتبر."); return
    await state.update_data(amount=amount)
    await state.set_state(AdminChargeFSM.waiting_description)
    await message.answer("📝 توضیحات:")

@router.message(AdminChargeFSM.waiting_description)
async def fsm_charge_desc(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    await state.clear()
    user = await crud.update_balance(session, data["target_user_id"], data["amount"], message.text.strip())
    action = "شارژ ✅" if data["amount"] >= 0 else "کسر ✅"
    await message.answer(
        f"{action}\nکاربر: {data['target_user_id']}\n"
        f"مبلغ: {abs(data['amount']):,.0f} تومان\n"
        f"موجودی جدید: {user.balance:,.0f} تومان",
        reply_markup=back_to_admin_kb(),
    )


# ── مدیریت بسته‌ها ────────────────────────────

@router.callback_query(F.data == "admin_tariffs")
async def cb_admin_tariffs(query: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True); return
    tariffs = await crud.get_active_tariffs(session)
    await query.message.edit_text(
        "📦 <b>بسته‌های فعال</b>" if tariffs else "📦 هیچ بسته‌ای تعریف نشده.",
        reply_markup=admin_tariffs_kb(tariffs),
    )
    await query.answer()

@router.callback_query(F.data == "add_tariff")
async def cb_add_tariff(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True); return
    await state.set_state(AdminAddTariffFSM.waiting_name)
    await query.message.edit_text("➕ نام بسته را وارد کنید:\n<i>مثال: ۱۰ گیگ ۳۰ روزه</i>")
    await query.answer()

@router.message(AdminAddTariffFSM.waiting_name)
async def fsm_tariff_name(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id): return
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminAddTariffFSM.waiting_data_gb)
    await message.answer("📦 حجم به GB:")

@router.message(AdminAddTariffFSM.waiting_data_gb)
async def fsm_tariff_gb(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id): return
    try:
        gb = float(message.text.strip())
    except ValueError:
        await message.answer("⚠️ عدد وارد کنید."); return
    await state.update_data(data_limit_gb=gb)
    await state.set_state(AdminAddTariffFSM.waiting_days)
    await message.answer("📅 مدت به روز:")

@router.message(AdminAddTariffFSM.waiting_days)
async def fsm_tariff_days(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id): return
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ عدد صحیح وارد کنید."); return
    await state.update_data(duration_days=days)
    await state.set_state(AdminAddTariffFSM.waiting_price)
    await message.answer("💰 قیمت به تومان:")

@router.message(AdminAddTariffFSM.waiting_price)
async def fsm_tariff_price(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not is_admin(message.from_user.id): return
    try:
        price = float(message.text.strip().replace(",", ""))
    except ValueError:
        await message.answer("⚠️ مبلغ نامعتبر."); return
    data = await state.get_data()
    await state.clear()
    tariff = await crud.create_tariff(session, data["name"], data["data_limit_gb"], data["duration_days"], price)
    await message.answer(
        f"✅ بسته ساخته شد!\n\nID: <b>{tariff.id}</b>\n{tariff.name}\n"
        f"{tariff.data_limit_gb}GB | {tariff.duration_days}روز | {tariff.price:,.0f}T",
        reply_markup=back_to_admin_kb(),
    )

@router.callback_query(F.data.startswith("del_tariff:"))
async def cb_del_tariff(query: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True); return
    await crud.delete_tariff(session, int(query.data.split(":")[1]))
    await query.answer("✅ بسته غیرفعال شد.", show_alert=True)
    tariffs = await crud.get_active_tariffs(session)
    await query.message.edit_reply_markup(reply_markup=admin_tariffs_kb(tariffs))

@router.callback_query(F.data.startswith("edit_tariff:"))
async def cb_edit_tariff(query: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True); return
    tariff_id = int(query.data.split(":")[1])
    tariff = await crud.get_tariff(session, tariff_id)
    if not tariff:
        await query.answer("یافت نشد!", show_alert=True); return
    await state.update_data(edit_tariff_id=tariff_id)
    await state.set_state(AdminEditTariffFSM.waiting_field)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="📛 نام",      callback_data="ef:name")
    kb.button(text="📦 حجم",      callback_data="ef:data_limit_gb")
    kb.button(text="📅 مدت",      callback_data="ef:duration_days")
    kb.button(text="💰 قیمت",     callback_data="ef:price")
    kb.button(text="🔙 لغو",      callback_data="admin_tariffs")
    kb.adjust(2, 2, 1)
    await query.message.edit_text(
        f"✏️ <b>{tariff.name}</b>\n{tariff.data_limit_gb}GB | {tariff.duration_days}روز | {tariff.price:,.0f}T\n\nکدام فیلد؟",
        reply_markup=kb.as_markup(),
    )
    await query.answer()

@router.callback_query(F.data.startswith("ef:"), AdminEditTariffFSM.waiting_field)
async def cb_ef(query: CallbackQuery, state: FSMContext) -> None:
    field = query.data.split(":")[1]
    await state.update_data(edit_field=field)
    await state.set_state(AdminEditTariffFSM.waiting_value)
    labels = {"name": "نام جدید", "data_limit_gb": "حجم جدید (GB)", "duration_days": "مدت جدید (روز)", "price": "قیمت جدید (تومان)"}
    await query.message.edit_text(f"✏️ {labels.get(field, field)}:")
    await query.answer()

@router.message(AdminEditTariffFSM.waiting_value)
async def fsm_ef_value(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    await state.clear()
    tariff = await crud.get_tariff(session, data["edit_tariff_id"])
    if not tariff:
        await message.answer("❌ یافت نشد."); return
    raw = message.text.strip().replace(",", "")
    try:
        f = data["edit_field"]
        if f == "name":             tariff.name = raw
        elif f == "data_limit_gb":  tariff.data_limit_gb = float(raw)
        elif f == "duration_days":  tariff.duration_days = int(raw)
        elif f == "price":          tariff.price = float(raw)
    except ValueError:
        await message.answer("⚠️ مقدار نامعتبر."); return
    await message.answer(f"✅ {tariff.name} بروزرسانی شد.", reply_markup=back_to_admin_kb())


# ── تنظیم Inbound ─────────────────────────────

@router.callback_query(F.data == "admin_inbound")
async def cb_admin_inbound(query: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True); return
    current = await crud.get_setting(session, "active_inbound_id") or "تنظیم نشده"
    await state.set_state(AdminInboundFSM.waiting_inbound_id)
    await query.message.edit_text(
        f"⚙️ Inbound فعلی: <b>#{current}</b>\n\n"
        "شناسه جدید را وارد کنید:\n<i>برای دیدن لیست: /inbounds</i>"
    )
    await query.answer()

@router.message(AdminInboundFSM.waiting_inbound_id)
async def fsm_inbound(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not is_admin(message.from_user.id): return
    if not message.text.strip().isdigit():
        await message.answer("⚠️ عدد صحیح وارد کنید."); return
    await state.clear()
    await crud.set_setting(session, "active_inbound_id", message.text.strip())
    await message.answer(f"✅ Inbound به #{message.text.strip()} تغییر یافت.", reply_markup=back_to_admin_kb())


# ── مدیریت کاربران ────────────────────────────

@router.callback_query(F.data == "admin_users")
async def cb_admin_users(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True); return
    await state.set_state(AdminUserSearchFSM.waiting_query)
    await query.message.edit_text("👥 آیدی عددی یا یوزرنیم کاربر را وارد کنید:")
    await query.answer()

@router.message(AdminUserSearchFSM.waiting_query)
async def fsm_user_search(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not is_admin(message.from_user.id): return
    q = message.text.strip().lstrip("@")
    await state.clear()
    user = None
    if q.isdigit():
        user = await crud.get_user(session, int(q))
    else:
        users = await crud.search_user_by_username(session, q)
        user = users[0] if users else None
    if not user:
        await message.answer("❌ یافت نشد.", reply_markup=back_to_admin_kb()); return
    from keyboards.inline import admin_user_kb
    await message.answer(
        f"👤 <b>{user.full_name}</b>\n🆔 <code>{user.id}</code>\n"
        f"💰 {user.balance:,.0f}T | 📦 {len(user.configs)} سرویس\n"
        f"{'🔴 مسدود' if user.is_banned else '🟢 فعال'}",
        reply_markup=admin_user_kb(user.id),
    )

@router.callback_query(F.data.startswith("ban_user:"))
async def cb_ban(query: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if not is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True); return
    uid = int(query.data.split(":")[1])
    await crud.set_user_banned(session, uid, True)
    try: await bot.send_message(uid, "⛔ حساب شما مسدود شده.")
    except Exception: pass
    await query.answer("✅ مسدود شد.", show_alert=True)

@router.callback_query(F.data.startswith("unban_user:"))
async def cb_unban(query: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if not is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True); return
    uid = int(query.data.split(":")[1])
    await crud.set_user_banned(session, uid, False)
    try: await bot.send_message(uid, "✅ مسدودیت برداشته شد.")
    except Exception: pass
    await query.answer("✅ رفع مسدودیت.", show_alert=True)

@router.callback_query(F.data.startswith("quick_charge:"))
async def cb_quick_charge(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True); return
    uid = int(query.data.split(":")[1])
    await state.update_data(target_user_id=uid)
    await state.set_state(AdminChargeFSM.waiting_amount)
    await query.message.edit_text(f"💳 شارژ/کسر برای <code>{uid}</code>\nمبلغ:")
    await query.answer()


# ── دستورات متنی ──────────────────────────────

@router.message(Command("inbounds"))
async def cmd_inbounds(message: Message) -> None:
    if not is_admin(message.from_user.id): return
    from services.xui_api import xui_client
    wait = await message.answer("⏳ در حال دریافت...")
    inbounds = await xui_client.get_inbounds()
    if not inbounds:
        await wait.edit_text("❌ خطا در اتصال یا هیچ inbound‌ای وجود ندارد."); return
    lines = ["📡 <b>Inbound‌های پنل:</b>\n"]
    for ib in inbounds:
        lines.append(
            f"{'✅' if ib.get('enable') else '❌'} "
            f"ID=<b>{ib.get('id')}</b> | "
            f"<b>{ib.get('protocol','?').upper()}</b>:{ib.get('port','?')} | "
            f"{ib.get('remark','—')}"
        )
    lines.append("\n💡 با /admin → تنظیم Inbound شناسه را ست کنید.")
    await wait.edit_text("\n".join(lines))

@router.message(Command("user"))
async def cmd_user(message: Message, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id): return
    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("استفاده: /user <user_id>"); return
    user = await crud.get_user(session, int(parts[1]))
    if not user:
        await message.answer("❌ یافت نشد."); return
    from keyboards.inline import admin_user_kb
    await message.answer(
        f"👤 {user.full_name}\n🆔 {user.id}\n💰 {user.balance:,.0f}T\n"
        f"📦 {len(user.configs)} سرویس\n{'🔴 مسدود' if user.is_banned else '🟢 فعال'}",
        reply_markup=admin_user_kb(user.id),
    )

@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id): return
    from sqlalchemy import select
    from sqlalchemy import func as sqlfunc
    from database.models import User, UserConfig, Transaction
    total_users  = (await session.execute(select(sqlfunc.count(User.id)))).scalar()
    active_users = (await session.execute(select(sqlfunc.count(User.id)).where(User.is_banned == False))).scalar()
    total_cfgs   = (await session.execute(select(sqlfunc.count(UserConfig.id)))).scalar()
    revenue      = (await session.execute(select(sqlfunc.sum(Transaction.amount)).where(Transaction.amount < 0))).scalar() or 0
    await message.answer(
        "📊 <b>آمار ربات</b>\n\n"
        f"👥 کل کاربران: <b>{total_users:,}</b>\n"
        f"✅ فعال: <b>{active_users:,}</b>\n"
        f"📦 سرویس فروخته‌شده: <b>{total_cfgs:,}</b>\n"
        f"💰 کل فروش: <b>{abs(revenue):,.0f} تومان</b>",
        reply_markup=back_to_admin_kb(),
    )

"""
هندلرهای کاربر
فلو خرید: انتخاب بسته → وارد کردن ایمیل → ساخت کلاینت در پنل → تحویل sub_link
"""

import logging
import re
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

import database.crud as crud
from keyboards.inline import back_to_main_kb, main_menu_kb, tariffs_kb, user_configs_kb
from services.xui_api import xui_client
from utils.states import BuyConfigFSM
from utils.decorator import require_user_and_text

logger = logging.getLogger(__name__)
router = Router(name="user")


@require_user_and_text
@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    
    assert message.from_user

    user = await crud.get_or_create_user(
        session, message.from_user.id,
        message.from_user.username, message.from_user.full_name,
    )
    if user.is_banned:
        await message.answer("⛔ حساب شما مسدود شده است.")
        return
    await message.answer(
        f"👋 سلام <b>{message.from_user.full_name}</b>!\n\n"
        f"💰 موجودی: <b>{user.balance:,.0f} تومان</b>",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(query: CallbackQuery, session: AsyncSession) -> None:
    user = await crud.get_user(session, query.from_user.id)
    balance = user.balance if user else 0.0
    
    text = f"🏠 <b>منوی اصلی</b>\n\n💰 موجودی: <b>{balance:,.0f} تومان</b>"
    
    # ── فیکس Pylance (edit_text) ──
    if isinstance(query.message, Message):
        await query.message.edit_text(text, reply_markup=main_menu_kb())
    await query.answer()


@router.callback_query(F.data == "show_balance")
async def cb_show_balance(query: CallbackQuery, session: AsyncSession) -> None:
    user = await crud.get_user(session, query.from_user.id)
    if not user:
        await query.answer("کاربر یافت نشد!", show_alert=True)
        return
        
    text = f"💰 <b>موجودی کیف پول</b>\n\n<b>{user.balance:,.0f} تومان</b>"
    
    if isinstance(query.message, Message):
        await query.message.edit_text(text, reply_markup=back_to_main_kb())
    await query.answer()


@router.callback_query(F.data == "buy_config")
async def cb_buy_config(query: CallbackQuery, session: AsyncSession) -> None:
    tariffs = await crud.get_active_tariffs(session)
    if not tariffs:
        await query.answer("⚠️ بسته‌ای برای فروش وجود ندارد.", show_alert=True)
        return
        
    text = "📦 <b>انتخاب بسته</b>\n\nیک بسته را انتخاب کنید:"
    
    if isinstance(query.message, Message):
        await query.message.edit_text(text, reply_markup=tariffs_kb(tariffs))
    await query.answer()


@router.callback_query(F.data.startswith("tariff:"))
async def cb_select_tariff(query: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not query.data:
        await query.answer("خطا در دیتای ورودی!", show_alert=True)
        return
        
    data_parts = query.data.split(":")
    tariff_id = int(data_parts[1])
    
    tariff = await crud.get_tariff(session, tariff_id)
    user   = await crud.get_user(session, query.from_user.id)

    if not tariff or not user:
        await query.answer("خطا! دوباره تلاش کنید.", show_alert=True)
        return

    if user.balance < tariff.price:
        shortage = tariff.price - user.balance
        await query.answer(
            f"💸 موجودی کافی نیست!\nکمبود: {shortage:,.0f} تومان",
            show_alert=True,
        )
        return

    await query.answer()

    await state.update_data(tariff_id=tariff_id)
    await state.set_state(BuyConfigFSM.waiting_config_name)

    text = (
        f"✅ بسته: <b>{tariff.name}</b>\n"
        f"📦 حجم: {tariff.data_limit_gb:.0f}GB | مدت: {tariff.duration_days} روز\n"
        f"💰 قیمت: <b>{tariff.price:,.0f} تومان</b>\n\n"
        "📧 <b>ایمیل دلخواه</b> برای این سرویس را وارد کنید:\n"
        "<i>فقط حروف انگلیسی، اعداد، نقطه و خط تیره — بدون فاصله</i>\n"
        "<i>مثال: ali.rezaei یا user123</i>"
    )
    
    if isinstance(query.message, Message):
        await query.message.edit_text(text)


@require_user_and_text
@router.message(BuyConfigFSM.waiting_config_name)
async def process_email_input(message: Message, session: AsyncSession, state: FSMContext) -> None:

    assert message.from_user
    assert message.text

    raw_email = message.text.strip().lower()

    if not re.match(r'^[a-z0-9][a-z0-9.\-_]{1,30}[a-z0-9]$', raw_email):
        await message.answer(
            "⚠️ ایمیل نامعتبر است!\n\n"
            "• فقط حروف انگلیسی کوچک، اعداد، نقطه، خط تیره\n"
            "• بین ۳ تا ۳۲ کاراکتر\n"
            "• بدون فاصله\n\n"
            "دوباره وارد کنید:"
        )
        return

    data = await state.get_data()
    tariff_id: int = data["tariff_id"]

    tariff = await crud.get_tariff(session, tariff_id)
    user   = await crud.get_user(session, message.from_user.id)

    if not tariff or not user:
        await state.clear()
        await message.answer("❌ خطا. لطفاً دوباره از منو شروع کنید.", reply_markup=back_to_main_kb())
        return

    if user.balance < tariff.price:
        await state.clear()
        await message.answer("❌ موجودی کافی نیست.", reply_markup=back_to_main_kb())
        return

    panel_email = f"{raw_email}_{message.from_user.id}"

    try:
        if hasattr(crud, 'get_config_by_email'):
            existing_cfg = await crud.get_config_by_email(session, panel_email)
            if existing_cfg:
                await message.answer(
                    f"⚠️ نام کاربری <code>{raw_email}</code> قبلاً توسط شما استفاده شده است.\n"
                    f"لطفاً یک نام دیگر وارد کنید:"
                )
                return
    except Exception as db_exc:
        logger.error("Error checking unique email in local db: %s", db_exc)

    await state.clear()

    inbound_str = await crud.get_setting(session, "active_inbound_id")
    inbound_id  = int(inbound_str) if inbound_str else 1

    processing = await message.answer("⏳ در حال ساخت سرویس...")

    try:
        created = await xui_client.add_client(
            inbound_id=inbound_id,
            email=panel_email,
            data_limit_gb=tariff.data_limit_gb,
            duration_days=tariff.duration_days,
        )
    except Exception as exc:
        logger.exception("add_client error for user %s: %s", message.from_user.id, exc)
        created = None

    if not created:
        await processing.edit_text(
            "❌ خطا در ساخت سرویس. لطفاً:\n"
            "۱. از صحیح بودن تنظیمات پنل مطمئن شوید (/admin)\n"
            "۲. دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.",
            reply_markup=back_to_main_kb(),
        )
        return

    try:
        await crud.update_balance(
            session, user.id, -tariff.price,
            description=f"خرید {tariff.name} | {panel_email}",
        )

        await crud.create_user_config(
            session,
            user_id=user.id,
            tariff_id=tariff_id,
            panel_email=created.email,
            panel_uuid=created.uuid,
            inbound_id=inbound_id,
            sub_link=created.sub_link,
            label=raw_email,
        )
    except Exception as db_err:
        logger.exception("Database insert crash after successful panel allocation: %s", db_err)
        await processing.edit_text(
            "⚠️ سرویس در پنل ساخته شد اما در ثبت دیتابیس ربات مشکلی رخ داد.\n"
            "لطفاً با پشتیبانی تماس بگیرید.",
            reply_markup=back_to_main_kb()
        )
        return

    new_balance = user.balance - tariff.price
    await processing.edit_text(
        f"🎉 <b>سرویس با موفقیت ساخته شد!</b>\n\n"
        f"📦 بسته: <b>{tariff.name}</b>\n"
        f"📧 ایمیل در پنل: <code>{panel_email}</code>\n"
        f"⏱ مدت: {tariff.duration_days} روز\n"
        f"💾 حجم: {tariff.data_limit_gb:.0f} GB\n\n"
        f"📡 <b>لینک اشتراک (Subscription):</b>\n"
        f"<code>{created.sub_link}</code>\n\n"
        f"<i>این لینک را در نرم‌افزار خود وارد کنید.</i>\n\n"
        f"💰 موجودی باقی‌مانده: <b>{new_balance:,.0f} تومان</b>",
        reply_markup=back_to_main_kb(),
    )


@router.callback_query(F.data == "my_configs")
async def cb_my_configs(query: CallbackQuery, session: AsyncSession) -> None:
    configs = await crud.get_user_configs(session, query.from_user.id)
    if not configs:
        await query.answer("هنوز سرویسی خریداری نکرده‌اید.", show_alert=True)
        return
        
    if isinstance(query.message, Message):
        await query.message.edit_text(
            "📋 <b>سرویس‌های شما</b>",
            reply_markup=user_configs_kb(configs),
        )
    await query.answer()


@router.callback_query(F.data.startswith("config_info:"))
async def cb_config_info(query: CallbackQuery, session: AsyncSession) -> None:
    if not query.data:
        await query.answer("دیتای کالبک نامعتبر است!", show_alert=True)
        return
        
    data_parts = query.data.split(":")
    config_id = int(data_parts[1])
    
    cfg = await crud.get_config_by_id(session, config_id)

    if not cfg or cfg.user_id != query.from_user.id:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return

    await query.answer("⏳ در حال دریافت اطلاعات...")

    info = None
    try:
        info = await xui_client.get_client_info(cfg.panel_email)
    except Exception as exc:
        logger.exception("get_client_info error for %s: %s", cfg.panel_email, exc)

    label = cfg.label or cfg.panel_email
    text = f"🔑 <b>{label}</b>\n\n"

    if info:
        now_ts = datetime.now().timestamp() * 1000
        is_expired = info.expiry_time and (info.expiry_time.timestamp() * 1000 < now_ts)
        
        status = "✅ فعال" if info.enable and not is_expired else "❌ منقضی/غیرفعال"
        expiry = info.expiry_time.strftime("%Y/%m/%d") if info.expiry_time else "نامحدود"
        
        used_gb = (info.upload_bytes + info.download_bytes) / (1024 ** 3)
        remaining_gb = max(0.0, info.total_gb - used_gb) if info.total_gb > 0 else 0.0
        remaining_str = f"{remaining_gb:.2f} GB" if info.total_gb > 0 else "نامحدود"

        text += (
            f"📊 وضعیت: {status}\n"
            f"📦 حجم کل: <b>{info.total_gb:.1f} GB</b>\n"
            f"📤 مصرف شده: <b>{used_gb:.2f} GB</b>\n"
            f"📥 باقی‌مانده: <b>{remaining_str}</b>\n"
            f"📅 انقضا: <b>{expiry}</b>\n\n"
        )
    else:
        text += "⚠️ اطلاعات ترافیک در دسترس نیست.\n\n"

    text += f"📡 <b>لینک اشتراک:</b>\n<code>{cfg.sub_link}</code>"

    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 بروزرسانی", callback_data=f"config_info:{config_id}")
    kb.button(text="🔙 بازگشت",    callback_data="my_configs")
    kb.adjust(2)

    if isinstance(query.message, Message):
        await query.message.edit_text(text, reply_markup=kb.as_markup())

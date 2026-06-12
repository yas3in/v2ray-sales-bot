"""
سیستم پرداخت کارت‌به‌کارت
فلو:
  ۱. کاربر مبلغ و شماره کارت را می‌بیند
  ۲. رسید (عکس/متن) را ارسال می‌کند
  ۳. ادمین تأیید یا رد می‌کند
  ۴. در صورت تأیید، کیف پول شارژ می‌شود
"""

import logging
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    Message,
    PhotoSize,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

import database.crud as crud
from config import settings

logger = logging.getLogger(__name__)
router = Router(name="card_payment")


# ══════════════════════════════════════════════
#  FSM
# ══════════════════════════════════════════════

class CardPayFSM(StatesGroup):
    waiting_amount   = State()   # انتخاب مبلغ شارژ
    waiting_receipt  = State()   # انتظار رسید از کاربر


# ══════════════════════════════════════════════
#  شروع فرآیند — کاربر روی «شارژ کیف پول» کلیک می‌کند
# ══════════════════════════════════════════════

CHARGE_AMOUNTS = [50_000, 100_000, 200_000, 500_000]   # تومان


def charge_amounts_kb():
    builder = InlineKeyboardBuilder()
    for amt in CHARGE_AMOUNTS:
        builder.button(
            text=f"💳 {amt:,} تومان",
            callback_data=f"card_pay:{amt}",
        )
    builder.button(text="🔙 بازگشت", callback_data="main_menu")
    builder.adjust(2)
    return builder.as_markup()


@router.callback_query(F.data == "charge_wallet")
async def cb_charge_wallet(query: CallbackQuery) -> None:
    await query.message.edit_text(
        "💳 <b>شارژ کیف پول — کارت به کارت</b>\n\n"
        "مبلغ شارژ را انتخاب کنید:",
        reply_markup=charge_amounts_kb(),
    )
    await query.answer()


# ══════════════════════════════════════════════
#  انتخاب مبلغ → نمایش شماره کارت
# ══════════════════════════════════════════════

@router.callback_query(F.data.startswith("card_pay:"))
async def cb_card_pay_select(
    query: CallbackQuery, state: FSMContext
) -> None:
    amount = int(query.data.split(":")[1])
    await state.update_data(amount=amount, user_id=query.from_user.id)
    await state.set_state(CardPayFSM.waiting_receipt)

    card_number = settings.CARD_NUMBER
    card_owner  = settings.CARD_OWNER

    await query.message.edit_text(
        f"💳 <b>اطلاعات واریز</b>\n\n"
        f"مبلغ: <b>{amount:,} تومان</b>\n\n"
        f"شماره کارت:\n<code>{card_number}</code>\n"
        f"به نام: <b>{card_owner}</b>\n\n"
        "پس از واریز، <b>تصویر رسید</b> یا <b>کد پیگیری</b> را ارسال کنید.\n"
        "⚠️ درخواست پس از تأیید ادمین پردازش می‌شود."
    )
    await query.answer()


# ══════════════════════════════════════════════
#  دریافت رسید → ارسال به ادمین
# ══════════════════════════════════════════════

@router.message(CardPayFSM.waiting_receipt)
async def receive_receipt(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    data = await state.get_data()
    amount: int  = data["amount"]
    user_id: int = data["user_id"]
    await state.clear()

    user = await crud.get_user(session, user_id)
    username_str = f"@{user.username}" if user and user.username else "بدون یوزرنیم"

    # پیام تأیید برای ادمین
    admin_text = (
        f"📥 <b>درخواست شارژ کیف پول</b>\n\n"
        f"👤 کاربر: <b>{message.from_user.full_name}</b> ({username_str})\n"
        f"🆔 آیدی: <code>{user_id}</code>\n"
        f"💰 مبلغ: <b>{amount:,} تومان</b>\n\n"
        "رسید ارسالی کاربر 👇"
    )

    confirm_kb = InlineKeyboardBuilder()
    confirm_kb.button(
        text="✅ تأیید و شارژ",
        callback_data=f"confirm_charge:{user_id}:{amount}",
    )
    confirm_kb.button(
        text="❌ رد درخواست",
        callback_data=f"reject_charge:{user_id}:{amount}",
    )
    confirm_kb.adjust(2)

    for admin_id in settings.ADMIN_IDS:
        try:
            # ابتدا متن توضیحات
            await bot.send_message(admin_id, admin_text)

            # سپس رسید (عکس یا متن)
            if message.photo:
                await bot.send_photo(
                    admin_id,
                    photo=message.photo[-1].file_id,
                    reply_markup=confirm_kb.as_markup(),
                )
            elif message.document:
                await bot.send_document(
                    admin_id,
                    document=message.document.file_id,
                    reply_markup=confirm_kb.as_markup(),
                )
            else:
                # متن/کد پیگیری
                await bot.send_message(
                    admin_id,
                    f"📝 متن رسید:\n<code>{message.text}</code>",
                    reply_markup=confirm_kb.as_markup(),
                )
        except Exception as exc:
            logger.exception("Failed to notify admin %s: %s", admin_id, exc)

    await message.answer(
        "✅ <b>رسید دریافت شد!</b>\n\n"
        "پس از بررسی توسط ادمین، کیف پول شما شارژ خواهد شد.\n"
        "معمولاً کمتر از ۳۰ دقیقه طول می‌کشد."
    )


# ══════════════════════════════════════════════
#  ادمین: تأیید / رد پرداخت
# ══════════════════════════════════════════════

@router.callback_query(F.data.startswith("confirm_charge:"))
async def cb_confirm_charge(
    query: CallbackQuery,
    session: AsyncSession,
    bot: Bot,
) -> None:
    if query.from_user.id not in settings.ADMIN_IDS:
        await query.answer("⛔", show_alert=True)
        return

    _, user_id_str, amount_str = query.data.split(":")
    user_id = int(user_id_str)
    amount  = int(amount_str)

    try:
        await crud.update_balance(
            session,
            user_id=user_id,
            amount=amount,
            description=f"شارژ کارت به کارت — تأیید ادمین {query.from_user.id}",
        )

        # اطلاع به کاربر
        await bot.send_message(
            user_id,
            f"🎉 <b>کیف پول شما شارژ شد!</b>\n\n"
            f"💰 مبلغ: <b>{amount:,} تومان</b>\n"
            "برای خرید کانفیگ از منوی اصلی اقدام کنید.",
        )

        await query.message.edit_caption(
            caption=(query.message.caption or "") + f"\n\n✅ تأیید شد توسط {query.from_user.full_name}"
        ) if query.message.photo else await query.message.edit_text(
            (query.message.text or "") + f"\n\n✅ تأیید شد توسط {query.from_user.full_name}"
        )
        await query.answer("✅ شارژ انجام شد.", show_alert=True)

    except Exception as exc:
        logger.exception("confirm_charge error: %s", exc)
        await query.answer("❌ خطا در شارژ کیف پول.", show_alert=True)


@router.callback_query(F.data.startswith("reject_charge:"))
async def cb_reject_charge(
    query: CallbackQuery,
    bot: Bot,
) -> None:
    if query.from_user.id not in settings.ADMIN_IDS:
        await query.answer("⛔", show_alert=True)
        return

    _, user_id_str, amount_str = query.data.split(":")
    user_id = int(user_id_str)
    amount  = int(amount_str)

    await bot.send_message(
        user_id,
        f"❌ <b>درخواست شارژ رد شد.</b>\n\n"
        f"مبلغ: {amount:,} تومان\n"
        "در صورت سؤال با پشتیبانی تماس بگیرید.",
    )

    suffix = f"\n\n❌ رد شد توسط {query.from_user.full_name}"
    if query.message.photo:
        await query.message.edit_caption(caption=(query.message.caption or "") + suffix)
    else:
        await query.message.edit_text((query.message.text or "") + suffix)

    await query.answer("درخواست رد شد.", show_alert=True)

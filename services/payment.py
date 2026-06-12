"""
سرویس پرداخت زرین‌پال (Async)
فلو: درخواست پرداخت → دریافت authority → ریدایرکت کاربر → verify بعد از بازگشت
"""

import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

from config import settings

logger = logging.getLogger(__name__)

ZARINPAL_REQUEST_URL = "https://api.zarinpal.com/pg/v4/payment/request.json"
ZARINPAL_VERIFY_URL  = "https://api.zarinpal.com/pg/v4/payment/verify.json"
ZARINPAL_PAYMENT_URL = "https://www.zarinpal.com/pg/StartPay/{authority}"

# برای تست از sandbox استفاده کنید:
# ZARINPAL_REQUEST_URL = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
# ZARINPAL_VERIFY_URL  = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
# ZARINPAL_PAYMENT_URL = "https://sandbox.zarinpal.com/pg/StartPay/{authority}"


@dataclass
class PaymentRequest:
    authority: str
    payment_url: str


@dataclass
class PaymentVerify:
    success: bool
    ref_id: Optional[str] = None
    message: str = ""


class ZarinpalService:
    def __init__(self) -> None:
        self.merchant_id: str = settings.ZARINPAL_MERCHANT_ID
        self.callback_url: str = settings.ZARINPAL_CALLBACK_URL

    async def request_payment(
        self,
        amount_toman: int,
        description: str,
        user_id: int,
    ) -> Optional[PaymentRequest]:
        """
        ایجاد درخواست پرداخت
        amount_toman: مبلغ به تومان (زرین‌پال به ریال نیاز دارد → ×۱۰)
        """
        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount_toman * 10,       # تبدیل به ریال
            "description": description,
            "callback_url": f"{self.callback_url}?user_id={user_id}",
            "metadata": {"user_id": str(user_id)},
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    ZARINPAL_REQUEST_URL,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    data = await resp.json()

            errors = data.get("errors", {})
            if errors:
                logger.error("Zarinpal request error: %s", errors)
                return None

            authority = data["data"]["authority"]
            payment_url = ZARINPAL_PAYMENT_URL.format(authority=authority)
            logger.info("Zarinpal authority created: %s for user %s", authority, user_id)
            return PaymentRequest(authority=authority, payment_url=payment_url)

        except Exception as exc:
            logger.exception("Zarinpal request exception: %s", exc)
            return None

    async def verify_payment(
        self,
        authority: str,
        amount_toman: int,
    ) -> PaymentVerify:
        """
        تأیید پرداخت پس از بازگشت کاربر از درگاه
        """
        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount_toman * 10,
            "authority": authority,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    ZARINPAL_VERIFY_URL,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    data = await resp.json()

            code = data.get("data", {}).get("code", -1)
            ref_id = str(data.get("data", {}).get("ref_id", ""))

            if code in (100, 101):   # 100=موفق، 101=قبلاً تأیید شده
                logger.info("Zarinpal verify OK: ref_id=%s authority=%s", ref_id, authority)
                return PaymentVerify(success=True, ref_id=ref_id, message="پرداخت موفق")

            errors = data.get("errors", {})
            logger.warning("Zarinpal verify failed: code=%s errors=%s", code, errors)
            return PaymentVerify(success=False, message=f"خطای درگاه: کد {code}")

        except Exception as exc:
            logger.exception("Zarinpal verify exception: %s", exc)
            return PaymentVerify(success=False, message="خطای اتصال به درگاه")


zarinpal = ZarinpalService()

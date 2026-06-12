"""
تنظیمات مرکزی پروژه
تمام مقادیر از environment variables یا فایل .env خوانده می‌شوند.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    # ───── Telegram Bot ─────
    BOT_TOKEN: str
    ADMIN_IDS: List[int]

    # ───── Sanaei X-UI Panel ─────
    XUI_BASE_URL: str
    XUI_USERNAME: str
    XUI_PASSWORD: str

    # ───── Database ─────
    DATABASE_URL: str

    DEFAULT_INBOUND_ID: int

    SUB_DOMAIN: str
    SUB_PORT:   str
    SUB_PATH:   str

    # Webhook
    WEBHOOK_BASE_URL: str = "https://your-domain.com"
    WEBHOOK_PORT:     int  = 8080

    # کارت به کارت
    CARD_NUMBER: str = "6037-XXXX-XXXX-XXXX"
    CARD_OWNER:  str = "نام صاحب حساب"

    # زرین‌پال
    ZARINPAL_MERCHANT_ID:  str = "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
    ZARINPAL_CALLBACK_URL: str = "https://your-domain.com/payment/verify"


    model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore"
        )

try:
    settings = Settings() # type: ignore
except Exception as e:
    print(f"خطا در بارگذاری تنظیمات یا فایل .env:\n{e}")
    raise e

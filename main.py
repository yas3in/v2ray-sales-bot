"""
V2Ray Config Sales Bot — Entry Point (Polling Mode)
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from database.engine import init_db
from handlers import admin_router, user_router, payment_router
from middlewares.db_middleware import DatabaseMiddleware
from middlewares.query_answer_middleware import AutoAnswerMiddleware
from services.xui_api import xui_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("🚀 Starting V2Ray Sales Bot...")

    await init_db()
    logger.info("✅ Database initialized.")

    await xui_client.login()
    logger.info("✅ XUI panel authenticated.")

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())

    # ── Middlewares ───────────────────────────
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    # AutoAnswer: جلوگیری از "query is too old"
    dp.callback_query.middleware(AutoAnswerMiddleware())

    # ── Routers ───────────────────────────────
    dp.include_router(admin_router)
    dp.include_router(payment_router)
    dp.include_router(user_router)

    logger.info("✅ All routers registered.")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await xui_client.close()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())

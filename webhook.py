"""
Webhook Entry Point — جایگزین polling برای محیط production
از aiohttp به عنوان web server استفاده می‌کند (بدون نیاز به FastAPI).
"""

import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    setup_application,
)

from config import settings
from database.engine import init_db
from handlers import admin_router, user_router
from handlers.payment import router as payment_router
from middlewares.db_middleware import DatabaseMiddleware
from services.xui_api import xui_client


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

WEBHOOK_PATH   = f"/webhook/{settings.BOT_TOKEN}"
WEBHOOK_URL    = f"{settings.WEBHOOK_BASE_URL}{WEBHOOK_PATH}"


async def on_startup(bot: Bot) -> None:
    await init_db()
    logger.info("✅ DB initialized.")

    await xui_client.login()
    logger.info("✅ XUI client authenticated.")

    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query", "pre_checkout_query"],
    )
    logger.info("✅ Webhook set: %s", WEBHOOK_URL)


async def on_shutdown(bot: Bot) -> None:
    await bot.delete_webhook()
    await xui_client.close()
    logger.info("Bot shut down cleanly.")


def create_app() -> web.Application:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())

    dp.include_router(admin_router)
    dp.include_router(payment_router)
    dp.include_router(user_router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # Health check endpoint
    async def health(_: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    app.router.add_get("/health", health)

    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=settings.WEBHOOK_PORT)

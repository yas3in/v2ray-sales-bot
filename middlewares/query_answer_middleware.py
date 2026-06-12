"""
Middleware که مطمئن می‌شود هر CallbackQuery حتماً answer بگیرد.
اگر handler فراموش کند query.answer() صدا بزند یا خطا بخورد،
این middleware به صورت خودکار answer می‌دهد.
"""

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

logger = logging.getLogger(__name__)


class AutoAnswerMiddleware(BaseMiddleware):
    """
    قبل از اجرای handler یک flag می‌گذاریم.
    بعد از اتمام، اگر query هنوز answer نشده بود، خودمان answer می‌دهیم.
    """

    async def __call__(
        self,
        handler: Callable[[CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)

        result = None
        try:
            result = await handler(event, data)
        except Exception:
            raise
        finally:
            # اگر query هنوز answer نشده بود، یک answer خالی بفرست
            try:
                await event.answer()
            except TelegramBadRequest as e:
                if "query is too old" in str(e) or "query ID is invalid" in str(e):
                    # قبلاً answer شده یا منقضی شده — مشکلی نیست
                    pass
                else:
                    logger.debug("AutoAnswer skipped: %s", e)
            except Exception:
                pass

        return result

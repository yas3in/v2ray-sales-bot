from handlers.admin import router as admin_router
from handlers.user import router as user_router
from handlers.payment import router as payment_router

__all__ = ["admin_router", "user_router", "payment_router"]

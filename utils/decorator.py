from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession


def require_user_and_text(func):
    def wrapper(message: Message, session: AsyncSession):
        if not message.from_user or not message.text:
            return
        return func(message, session)
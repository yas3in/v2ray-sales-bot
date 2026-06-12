from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from config import settings
from database.models import Base

engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)

AsyncSessionFactory = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False, autocommit=False,
)

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # درج inbound_id پیش‌فرض
    async with AsyncSessionFactory() as session:
        from sqlalchemy import select
        r = await session.execute(select(Base.metadata.tables["bot_settings"]).where(
            Base.metadata.tables["bot_settings"].c.key == "active_inbound_id"
        ))
        if not r.fetchone():
            from database.models import BotSettings
            session.add(BotSettings(key="active_inbound_id", value=str(settings.DEFAULT_INBOUND_ID)))
            await session.commit()

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

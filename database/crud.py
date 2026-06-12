"""CRUD دیتابیس"""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import BotSettings, Tariff, Transaction, User, UserConfig


# ── User ──────────────────────────────────────

async def get_or_create_user(session: AsyncSession, user_id: int, username: Optional[str], full_name: str) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(id=user_id, username=username, full_name=full_name)
        session.add(user)
        await session.flush()
    return user

async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    r = await session.execute(select(User).where(User.id == user_id))
    return r.scalar_one_or_none()

async def update_balance(session: AsyncSession, user_id: int, amount: float, description: str) -> User:
    r = await session.execute(select(User).where(User.id == user_id))
    user = r.scalar_one()
    user.balance += amount
    session.add(Transaction(user_id=user_id, amount=amount, description=description))
    return user

async def set_user_banned(session: AsyncSession, user_id: int, banned: bool) -> bool:
    r = await session.execute(select(User).where(User.id == user_id))
    user = r.scalar_one_or_none()
    if not user:
        return False
    user.is_banned = banned
    return True

async def get_all_users(session: AsyncSession, limit: int = 50, offset: int = 0) -> List[User]:
    r = await session.execute(select(User).order_by(User.created_at.desc()).limit(limit).offset(offset))
    return list(r.scalars().all())

async def search_user_by_username(session: AsyncSession, username: str) -> List[User]:
    r = await session.execute(select(User).where(User.username.ilike(f"%{username}%")))
    return list(r.scalars().all())


# ── Tariff ────────────────────────────────────

async def get_active_tariffs(session: AsyncSession) -> List[Tariff]:
    r = await session.execute(select(Tariff).where(Tariff.is_active == True).order_by(Tariff.price))
    return list(r.scalars().all())

async def get_tariff(session: AsyncSession, tariff_id: int) -> Optional[Tariff]:
    r = await session.execute(select(Tariff).where(Tariff.id == tariff_id))
    return r.scalar_one_or_none()

async def create_tariff(session: AsyncSession, name: str, data_limit_gb: float, duration_days: int, price: float) -> Tariff:
    t = Tariff(name=name, data_limit_gb=data_limit_gb, duration_days=duration_days, price=price)
    session.add(t)
    await session.flush()
    return t

async def delete_tariff(session: AsyncSession, tariff_id: int) -> bool:
    r = await session.execute(select(Tariff).where(Tariff.id == tariff_id))
    t = r.scalar_one_or_none()
    if t:
        t.is_active = False
        return True
    return False


# ── UserConfig ────────────────────────────────

async def create_user_config(
    session: AsyncSession,
    user_id: int,
    tariff_id: int,
    panel_email: str,
    panel_uuid: str,
    panel_sub_id: str,
    inbound_id: int,
    sub_link: str,
    label: Optional[str] = None,
) -> UserConfig:
    cfg = UserConfig(
        user_id=user_id, tariff_id=tariff_id,
        panel_email=panel_email, panel_uuid=panel_uuid,
        panel_sub_id=panel_sub_id, inbound_id=inbound_id,
        sub_link=sub_link, label=label,
    )
    session.add(cfg)
    await session.flush()
    return cfg

async def get_user_configs(session: AsyncSession, user_id: int) -> List[UserConfig]:
    r = await session.execute(
        select(UserConfig)
        .where(UserConfig.user_id == user_id, UserConfig.is_active == True)
        .order_by(UserConfig.purchased_at.desc())
    )
    return list(r.scalars().all())

async def get_config_by_id(session: AsyncSession, config_id: int) -> Optional[UserConfig]:
    r = await session.execute(select(UserConfig).where(UserConfig.id == config_id))
    return r.scalar_one_or_none()

# ── اضافه شده جهت فیکس ارور هندلر و دیتابیس لوکال ──
async def get_config_by_email(session: AsyncSession, panel_email: str) -> Optional[UserConfig]:
    """بررسی وجود کانفیگ در دیتابیس محلی برای جلوگیری از خطای یونیک کانتیرنت"""
    r = await session.execute(select(UserConfig).where(UserConfig.panel_email == panel_email))
    return r.scalar_one_or_none()


# ── BotSettings ───────────────────────────────

async def get_setting(session: AsyncSession, key: str) -> Optional[str]:
    r = await session.execute(select(BotSettings).where(BotSettings.key == key))
    row = r.scalar_one_or_none()
    return row.value if row else None

async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    r = await session.execute(select(BotSettings).where(BotSettings.key == key))
    row = r.scalar_one_or_none()
    if row:
        row.value = value
    else:
        session.add(BotSettings(key=key, value=value))
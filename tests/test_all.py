"""
تست‌های واحد — pytest + pytest-asyncio
اجرا: pytest tests/ -v
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from database.models import Base, User, Tariff
import database.crud as crud
from services.xui_api import XUIClient, ClientInfo


# ══════════════════════════════════════════════
#  Fixtures دیتابیس — SQLite In-Memory برای تست
# ══════════════════════════════════════════════

@pytest_asyncio.fixture
async def db_session():
    """یک session دیتابیس موقت برای هر تست"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()

    await engine.dispose()


# ══════════════════════════════════════════════
#  تست‌های CRUD کاربر
# ══════════════════════════════════════════════

class TestUserCRUD:
    @pytest.mark.asyncio
    async def test_create_new_user(self, db_session: AsyncSession):
        """کاربر جدید باید ساخته شود و موجودی صفر داشته باشد"""
        user = await crud.get_or_create_user(
            db_session, user_id=111, username="testuser", full_name="Test User"
        )
        await db_session.commit()

        assert user.id == 111
        assert user.balance == 0.0
        assert user.is_banned is False

    @pytest.mark.asyncio
    async def test_get_existing_user_no_duplicate(self, db_session: AsyncSession):
        """فراخوانی دوباره نباید کاربر تکراری بسازد"""
        user1 = await crud.get_or_create_user(
            db_session, user_id=222, username="u", full_name="A"
        )
        await db_session.commit()

        user2 = await crud.get_or_create_user(
            db_session, user_id=222, username="u", full_name="A"
        )
        assert user1.id == user2.id

    @pytest.mark.asyncio
    async def test_update_balance_charge(self, db_session: AsyncSession):
        """شارژ کیف پول باید موجودی را افزایش دهد"""
        await crud.get_or_create_user(
            db_session, user_id=333, username=None, full_name="Wallet User"
        )
        await db_session.commit()

        user = await crud.update_balance(
            db_session, user_id=333, amount=100_000, description="شارژ تست"
        )
        await db_session.commit()

        assert user.balance == 100_000.0

    @pytest.mark.asyncio
    async def test_update_balance_deduct(self, db_session: AsyncSession):
        """کسر موجودی باید موجودی را کاهش دهد"""
        await crud.get_or_create_user(
            db_session, user_id=444, username=None, full_name="Deduct User"
        )
        await crud.update_balance(db_session, 444, 200_000, "شارژ اولیه")
        await db_session.commit()

        user = await crud.update_balance(db_session, 444, -50_000, "خرید بسته")
        await db_session.commit()

        assert user.balance == 150_000.0


# ══════════════════════════════════════════════
#  تست‌های CRUD تعرفه
# ══════════════════════════════════════════════

class TestTariffCRUD:
    @pytest.mark.asyncio
    async def test_create_tariff(self, db_session: AsyncSession):
        tariff = await crud.create_tariff(
            db_session,
            name="۱۰ گیگ ۳۰ روزه",
            data_limit_gb=10.0,
            duration_days=30,
            price=150_000,
        )
        await db_session.commit()

        assert tariff.id is not None
        assert tariff.is_active is True
        assert tariff.data_limit_gb == 10.0

    @pytest.mark.asyncio
    async def test_get_active_tariffs(self, db_session: AsyncSession):
        await crud.create_tariff(db_session, "بسته الف", 5.0, 30, 80_000)
        await crud.create_tariff(db_session, "بسته ب", 20.0, 30, 250_000)
        await db_session.commit()

        tariffs = await crud.get_active_tariffs(db_session)
        assert len(tariffs) == 2
        # باید بر اساس قیمت مرتب باشد
        assert tariffs[0].price <= tariffs[1].price

    @pytest.mark.asyncio
    async def test_soft_delete_tariff(self, db_session: AsyncSession):
        tariff = await crud.create_tariff(db_session, "حذفی", 10.0, 30, 100_000)
        await db_session.commit()

        result = await crud.delete_tariff(db_session, tariff.id)
        await db_session.commit()

        assert result is True
        active = await crud.get_active_tariffs(db_session)
        assert all(t.id != tariff.id for t in active)


# ══════════════════════════════════════════════
#  تست‌های سرویس XUI API (با Mock)
# ══════════════════════════════════════════════

class TestXUIClient:
    @pytest.mark.asyncio
    async def test_login_success(self):
        client = XUIClient()

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"success": True})

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))

        with patch.object(client, "_get_session", AsyncMock(return_value=mock_session)):
            result = await client.login()

        assert result is True
        assert client._logged_in is True

    @pytest.mark.asyncio
    async def test_login_failure(self):
        client = XUIClient()

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"success": False, "msg": "wrong password"})

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))

        with patch.object(client, "_get_session", AsyncMock(return_value=mock_session)):
            result = await client.login()

        assert result is False
        assert client._logged_in is False

    @pytest.mark.asyncio
    async def test_get_client_info_parses_correctly(self):
        client = XUIClient()
        client._logged_in = True

        mock_data = {
            "success": True,
            "obj": {
                "email": "testuser_123",
                "id": "some-uuid",
                "total": 10 * 1024 ** 3,   # 10 GB
                "up": 1 * 1024 ** 3,        # 1 GB upload
                "down": 2 * 1024 ** 3,      # 2 GB download
                "expiryTime": 1_800_000_000_000,
                "enable": True,
            },
        }

        with patch.object(client, "_get", AsyncMock(return_value=mock_data)):
            info = await client.get_client_info("testuser_123")

        assert info is not None
        assert info.total_gb == pytest.approx(10.0, rel=1e-3)
        assert info.used_gb  == pytest.approx(3.0, rel=1e-3)
        assert info.remaining_gb == pytest.approx(7.0, rel=1e-3)
        assert info.enable is True

    @pytest.mark.asyncio
    async def test_get_client_info_not_found(self):
        client = XUIClient()
        client._logged_in = True

        with patch.object(client, "_get", AsyncMock(return_value={"success": False})):
            info = await client.get_client_info("nonexistent")

        assert info is None

    def test_build_sub_link(self):
        client = XUIClient()
        link = client.build_sub_link("test-uuid-1234")
        assert "test-uuid-1234" in link
        assert link.startswith("http")


# ══════════════════════════════════════════════
#  تست BotSettings
# ══════════════════════════════════════════════

class TestBotSettings:
    @pytest.mark.asyncio
    async def test_set_and_get_setting(self, db_session: AsyncSession):
        await crud.set_setting(db_session, "active_inbound_id", "3")
        await db_session.commit()

        val = await crud.get_setting(db_session, "active_inbound_id")
        assert val == "3"

    @pytest.mark.asyncio
    async def test_update_existing_setting(self, db_session: AsyncSession):
        await crud.set_setting(db_session, "active_inbound_id", "1")
        await db_session.commit()
        await crud.set_setting(db_session, "active_inbound_id", "5")
        await db_session.commit()

        val = await crud.get_setting(db_session, "active_inbound_id")
        assert val == "5"

    @pytest.mark.asyncio
    async def test_get_missing_setting_returns_none(self, db_session: AsyncSession):
        val = await crud.get_setting(db_session, "nonexistent_key")
        assert val is None

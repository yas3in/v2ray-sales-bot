"""
مدل‌های دیتابیس
فلو: کاربر خرید می‌کند → ربات کلاینت در پنل می‌سازد → sub_link برمی‌گردد
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(128))
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    configs: Mapped[List["UserConfig"]] = relationship(back_populates="user", lazy="selectin")
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="user", lazy="selectin")


class Tariff(Base):
    __tablename__ = "tariffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    data_limit_gb: Mapped[float] = mapped_column(Float)
    duration_days: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    configs: Mapped[List["UserConfig"]] = relationship(back_populates="tariff", lazy="selectin")


class UserConfig(Base):
    """سرویس خریداری‌شده — کلاینت توسط ربات در پنل ساخته می‌شود"""
    __tablename__ = "user_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    tariff_id: Mapped[int] = mapped_column(Integer, ForeignKey("tariffs.id"))

    # اطلاعات کلاینت ساخته‌شده در پنل
    panel_email: Mapped[str] = mapped_column(String(256), unique=True)
    panel_uuid: Mapped[str] = mapped_column(String(64))
    inbound_id: Mapped[int] = mapped_column(Integer)

    sub_link: Mapped[str] = mapped_column(Text)
    label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # نام دلخواه کاربر

    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="configs")
    tariff: Mapped["Tariff"] = relationship(back_populates="configs")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    amount: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="transactions")


class BotSettings(Base):
    __tablename__ = "bot_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)

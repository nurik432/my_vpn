from sqlalchemy import BigInteger, String, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram id
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(128))
    marzban_username: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Пробный период
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False)

    # Реферальная система
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    referral_count: Mapped[int] = mapped_column(Integer, default=0)
    referral_bonus_days: Mapped[int] = mapped_column(Integer, default=0)

    referrals: Mapped[list["User"]] = relationship("User", back_populates="referrer")
    referrer: Mapped["User | None"] = relationship("User", back_populates="referrals", remote_side=[id])
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="user")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="user")
    promocodes: Mapped[list["UserPromocode"]] = relationship("UserPromocode", back_populates="user")


class Promocode(Base):
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    discount_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bonus_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_uses: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    users: Mapped[list["UserPromocode"]] = relationship("UserPromocode", back_populates="promocode")


class UserPromocode(Base):
    __tablename__ = "user_promocodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    promocode_id: Mapped[int] = mapped_column(Integer, ForeignKey("promocodes.id"))
    used_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="promocodes")
    promocode: Mapped["Promocode"] = relationship("Promocode", back_populates="users")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    plan: Mapped[str] = mapped_column(String(32))  # basic, premium
    days: Mapped[int] = mapped_column(Integer)
    data_limit_gb: Mapped[int] = mapped_column(Integer, default=100)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship("User", back_populates="subscriptions")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(Integer)  # в Stars или копейках
    currency: Mapped[str] = mapped_column(String(16))  # XTR (stars), USDT, TON
    plan: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending, paid, failed
    telegram_payment_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="payments")
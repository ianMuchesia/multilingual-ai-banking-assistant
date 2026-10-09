"""ORM models: users, accounts, transactions, pending_actions, router_audit."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from bankchat.clock import utc_now

MONEY = Numeric(14, 2)


class Base(DeclarativeBase):
    pass


def _new_action_id() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(15))
    # NULL = a customer who exists only to receive transfers and cannot log in.
    password_hash: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    accounts: Mapped[list["Account"]] = relationship(back_populates="user", order_by="Account.id")


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("type IN ('savings', 'current')", name="ck_accounts_type"),
        CheckConstraint("balance >= 0", name="ck_accounts_balance_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(10))
    currency: Mapped[str] = mapped_column(String(3))
    balance: Mapped[Decimal] = mapped_column(MONEY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user: Mapped[User] = relationship(back_populates="accounts")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        # Both legs of an internal transfer share a reference, one row per account.
        UniqueConstraint("reference", "account_id", name="uq_transactions_reference_account"),
        CheckConstraint("direction IN ('in', 'out')", name="ck_transactions_direction"),
        CheckConstraint(
            "channel IN ('internal', 'pesalink', 'mpesa', 'till', 'paybill', 'salary', 'deposit')",
            name="ck_transactions_channel",
        ),
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        Index("ix_transactions_account_created", "account_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(20), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    direction: Mapped[str] = mapped_column(String(3))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    channel: Mapped[str] = mapped_column(String(10))
    counterparty: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    balance_after: Mapped[Decimal] = mapped_column(MONEY)

    account: Mapped[Account] = relationship()


class PendingAction(Base):
    __tablename__ = "pending_actions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'executed', 'cancelled', 'expired')", name="ck_pending_actions_status"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_action_id)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    intent: Mapped[str] = mapped_column(String(40))
    slots: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(10))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    executed_reference: Mapped[str | None] = mapped_column(String(20))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RouterAudit(Base):
    __tablename__ = "router_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    message: Mapped[str] = mapped_column(Text)
    router_mode: Mapped[str] = mapped_column(String(10))
    intent: Mapped[str] = mapped_column(String(40))
    route: Mapped[str] = mapped_column(String(10))
    score: Mapped[float] = mapped_column(Float)
    margin: Mapped[float] = mapped_column(Float)
    reasons: Mapped[list[str]] = mapped_column(JSON)
    latency_ms: Mapped[float] = mapped_column(Float)
    reply_kind: Mapped[str] = mapped_column(String(20))
    pending_action_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from yaft.db.session import Base


class Currency(Base):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))


class FxRate(Base):
    __tablename__ = "fx_rates"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    base: Mapped[str] = mapped_column(String(3), primary_key=True)
    quote: Mapped[str] = mapped_column(String(3), primary_key=True)
    rate: Mapped[float] = mapped_column(Float)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(16))
    currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"))
    archived: Mapped[int] = mapped_column(Integer, default=0)
    opening_balance_minor: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(16))
    emoji: Mapped[str | None] = mapped_column(String(8), nullable=True)
    archived: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        UniqueConstraint("name", "parent_id", name="uq_category_name_parent"),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(16))
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    base_amount_minor: Mapped[int] = mapped_column(Integer)
    fx_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    merchant: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    recurring_id: Mapped[int | None] = mapped_column(
        ForeignKey("recurring_rules.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (
        Index("ix_tx_account", "account_id", "occurred_at"),
        Index("ix_tx_category", "category_id", "occurred_at"),
    )


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    period: Mapped[str] = mapped_column(String(16), default="monthly")
    starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    alert_thresholds: Mapped[str] = mapped_column(Text, default="[0.8,1.0]")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    target_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    progress_mode: Mapped[str] = mapped_column(String(32))
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    archived: Mapped[int] = mapped_column(Integer, default=0)


class GoalContribution(Base):
    __tablename__ = "goal_contributions"

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id"))
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"))
    amount_minor: Mapped[int] = mapped_column(Integer)


class RecurringRule(Base):
    __tablename__ = "recurring_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    rrule: Mapped[str] = mapped_column(Text)
    template_json: Mapped[str] = mapped_column(Text)
    next_run_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_run_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[int] = mapped_column(Integer, default=1)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    kind: Mapped[str] = mapped_column(String(32))
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class AlertFired(Base):
    __tablename__ = "alerts_fired"

    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), primary_key=True)
    period_key: Mapped[str] = mapped_column(String(7), primary_key=True)
    threshold: Mapped[float] = mapped_column(Float, primary_key=True)
    fired_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

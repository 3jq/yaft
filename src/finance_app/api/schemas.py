from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AccountOut(BaseModel):
    id: int
    name: str
    kind: str
    currency: str
    archived: int
    opening_balance_minor: int


class AccountIn(BaseModel):
    name: str
    kind: str
    currency: str
    opening_balance_minor: int = 0


class CategoryOut(BaseModel):
    id: int
    name: str
    parent_id: int | None
    kind: str
    emoji: str | None
    archived: int


class CategoryIn(BaseModel):
    name: str
    parent_id: int | None = None
    kind: str
    emoji: str | None = None


class TransactionOut(BaseModel):
    id: int
    group_id: str | None
    occurred_at: datetime
    account_id: int
    category_id: int | None
    kind: str
    amount_minor: int
    currency: str
    base_amount_minor: int
    fx_rate: float | None
    merchant: str | None
    note: str | None
    source: str | None
    raw_input: str | None
    confidence: float | None
    deleted_at: datetime | None


class TransactionPatch(BaseModel):
    occurred_at: datetime | None = None
    account_id: int | None = None
    category_id: int | None = None
    amount_minor: int | None = None
    currency: str | None = None
    merchant: str | None = None
    note: str | None = None


class SummaryOut(BaseModel):
    base_currency: str
    month_label: str  # YYYY-MM
    total_expense_minor: int
    total_income_minor: int
    by_category: list[dict]
    account_balances: list[dict]


class SettingsOut(BaseModel):
    base_currency: str
    timezone: str
    default_account_id: int
    alert_thresholds_default: list[float]


class SettingsPatch(BaseModel):
    base_currency: str | None = None
    timezone: str | None = None
    default_account_id: int | None = None
    alert_thresholds_default: list[float] | None = None


class SplitIn(BaseModel):
    category_id: int
    amount_minor: int
    note: str | None = None


class SplitRequest(BaseModel):
    splits: list[SplitIn] = Field(min_length=2)

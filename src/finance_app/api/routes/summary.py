from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.api.auth import require_owner
from finance_app.api.routes.transactions import _session
from finance_app.api.schemas import SummaryOut
from finance_app.db.models import Account, Category, Setting, Transaction

router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.get("", response_model=SummaryOut)
async def get_summary(
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    base_row = (
        await session.execute(select(Setting).where(Setting.key == "base_currency"))
    ).scalar_one_or_none()
    base = base_row.value if base_row else "USD"

    today = dt.date.today()
    start = dt.datetime(today.year, today.month, 1)
    if today.month == 12:
        end = dt.datetime(today.year + 1, 1, 1)
    else:
        end = dt.datetime(today.year, today.month + 1, 1)

    rows = (
        await session.execute(
            select(Transaction).where(
                Transaction.deleted_at.is_(None),
                Transaction.occurred_at >= start,
                Transaction.occurred_at < end,
            )
        )
    ).scalars().all()

    total_exp = sum(t.base_amount_minor for t in rows if t.kind == "expense")
    total_inc = sum(t.base_amount_minor for t in rows if t.kind == "income")

    cat_index: dict[int | None, int] = {}
    for t in rows:
        if t.kind == "expense":
            cat_index[t.category_id] = cat_index.get(t.category_id, 0) + t.base_amount_minor
    cats = (await session.execute(select(Category))).scalars().all()
    cname = {c.id: c.name for c in cats}
    by_cat = [
        {"category_id": k, "name": cname.get(k, "(uncategorized)"), "expense_minor": v}
        for k, v in sorted(cat_index.items(), key=lambda kv: -kv[1])
    ]

    accs = (
        await session.execute(select(Account).where(Account.archived == 0))
    ).scalars().all()
    balances = []
    for a in accs:
        all_rows = (
            await session.execute(
                select(Transaction).where(
                    Transaction.account_id == a.id,
                    Transaction.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        bal = a.opening_balance_minor
        for t in all_rows:
            if t.kind in ("expense", "transfer_out"):
                bal -= t.amount_minor
            elif t.kind in ("income", "transfer_in"):
                bal += t.amount_minor
        balances.append({
            "account_id": a.id,
            "name": a.name,
            "balance_minor": bal,
            "currency": a.currency,
        })

    return SummaryOut(
        base_currency=base,
        month_label=f"{today.year:04d}-{today.month:02d}",
        total_expense_minor=total_exp,
        total_income_minor=total_inc,
        by_category=by_cat,
        account_balances=balances,
    )

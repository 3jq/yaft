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


@router.get("/networth_series")
async def networth_series(
    days: int = 30,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    """Return end-of-day net worth (base currency only) for the last N days."""
    base_row = (
        await session.execute(select(Setting).where(Setting.key == "base_currency"))
    ).scalar_one_or_none()
    base = base_row.value if base_row else "USD"

    today = dt.date.today()
    days = max(1, min(days, 365))
    start_day = today - dt.timedelta(days=days - 1)

    accs = (
        await session.execute(
            select(Account).where(Account.archived == 0, Account.currency == base)
        )
    ).scalars().all()
    opening_total = sum(a.opening_balance_minor for a in accs)
    acc_ids = [a.id for a in accs]

    if not acc_ids:
        return {
            "base_currency": base,
            "points": [
                {
                    "date": (start_day + dt.timedelta(days=i)).isoformat(),
                    "value_minor": 0,
                }
                for i in range(days)
            ],
        }

    rows = (
        await session.execute(
            select(Transaction)
            .where(
                Transaction.deleted_at.is_(None),
                Transaction.account_id.in_(acc_ids),
            )
            .order_by(Transaction.occurred_at)
        )
    ).scalars().all()

    end_of_day: dict[dt.date, int] = {}
    running = opening_total
    for t in rows:
        d = t.occurred_at.date()
        if t.kind in ("income", "transfer_in"):
            running += t.base_amount_minor
        elif t.kind in ("expense", "transfer_out"):
            running -= t.base_amount_minor
        end_of_day[d] = running

    sorted_days = sorted(end_of_day.keys())

    points: list[dict] = []
    cur = opening_total
    j = 0
    for d in sorted_days:
        if d < start_day:
            cur = end_of_day[d]
            j += 1
        else:
            break

    for i in range(days):
        d = start_day + dt.timedelta(days=i)
        while j < len(sorted_days) and sorted_days[j] <= d:
            cur = end_of_day[sorted_days[j]]
            j += 1
        points.append({"date": d.isoformat(), "value_minor": cur})

    return {"base_currency": base, "points": points}

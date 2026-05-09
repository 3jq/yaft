from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.db.models import Account, Goal, Transaction


async def _account_balance_total(session: AsyncSession) -> int:
    accs = (
        await session.execute(select(Account).where(Account.archived == 0))
    ).scalars().all()
    total = 0
    for a in accs:
        rows = (
            await session.execute(
                select(Transaction).where(
                    Transaction.account_id == a.id,
                    Transaction.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        bal = a.opening_balance_minor
        for t in rows:
            if t.kind in ("expense", "transfer_out"):
                bal -= t.amount_minor
            elif t.kind in ("income", "transfer_in"):
                bal += t.amount_minor
        total += bal
    return total


async def forecast(session: AsyncSession, today: dt.date) -> dict:
    start = dt.datetime.combine(today - dt.timedelta(days=90), dt.time.min)
    rows = (
        await session.execute(
            select(Transaction).where(
                Transaction.deleted_at.is_(None),
                Transaction.occurred_at >= start,
            )
        )
    ).scalars().all()

    daily: dict[dt.date, int] = {}
    for t in rows:
        d = t.occurred_at.date()
        if t.kind in ("expense", "transfer_out"):
            v = -t.base_amount_minor
        elif t.kind in ("income", "transfer_in"):
            v = t.base_amount_minor
        else:
            continue
        daily[d] = daily.get(d, 0) + v

    n = max(1, len(daily))
    avg_daily = sum(daily.values()) / n  # in base minor units

    # End-of-month projection: current month-to-date + avg_daily * remaining days.
    if today.month == 12:
        next_first = dt.date(today.year + 1, 1, 1)
    else:
        next_first = dt.date(today.year, today.month + 1, 1)
    days_in_month = (next_first - dt.date(today.year, today.month, 1)).days

    mtd_start = dt.datetime(today.year, today.month, 1)
    mtd_rows = [t for t in rows if t.occurred_at >= mtd_start]
    mtd_net = 0
    for t in mtd_rows:
        if t.kind in ("expense", "transfer_out"):
            mtd_net -= t.base_amount_minor
        elif t.kind in ("income", "transfer_in"):
            mtd_net += t.base_amount_minor

    days_left = days_in_month - today.day
    eom_net_minor = mtd_net + int(avg_daily * days_left)

    # Runway: total liquid balance / monthly burn (positive = burn rate)
    monthly_burn = -avg_daily * 30 if avg_daily < 0 else 0
    total_balance = await _account_balance_total(session)
    runway_months = total_balance / monthly_burn if monthly_burn > 0 else None

    # Days-to-each-goal using net contribution rate (positive)
    days_to_goal: dict[int, int | None] = {}
    pos_daily = avg_daily if avg_daily > 0 else 0
    goals = (
        await session.execute(select(Goal).where(Goal.archived == 0))
    ).scalars().all()
    for g in goals:
        if pos_daily <= 0:
            days_to_goal[g.id] = None
        else:
            from finance_app.domain.goals import progress_minor
            prog = await progress_minor(session, g)
            remaining = g.target_minor - prog
            days_to_goal[g.id] = int(remaining / pos_daily) if remaining > 0 else 0

    return {
        "avg_daily_minor": int(avg_daily),
        "eom_net_minor": eom_net_minor,
        "runway_months": runway_months,
        "days_to_goal": days_to_goal,
        "month_label": f"{today.year:04d}-{today.month:02d}",
    }

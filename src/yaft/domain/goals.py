from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yaft.db.models import Account, Goal, GoalContribution, Transaction


async def _account_balance(session: AsyncSession, account_id: int) -> int:
    acc = await session.get(Account, account_id)
    rows = (await session.execute(
        select(Transaction).where(
            Transaction.account_id == account_id,
            Transaction.deleted_at.is_(None),
        )
    )).scalars().all()
    bal = acc.opening_balance_minor
    for t in rows:
        if t.kind in ("expense", "transfer_out"):
            bal -= t.amount_minor
        elif t.kind in ("income", "transfer_in"):
            bal += t.amount_minor
    return bal


async def progress_minor(session: AsyncSession, goal: Goal) -> int:
    if goal.progress_mode == "account_linked" and goal.account_id:
        return await _account_balance(session, goal.account_id)
    rows = (await session.execute(
        select(GoalContribution).where(GoalContribution.goal_id == goal.id)
    )).scalars().all()
    return sum(c.amount_minor for c in rows)


async def projected_hit_date(session: AsyncSession, goal: Goal, today: dt.date) -> dt.date | None:
    progress = await progress_minor(session, goal)
    remaining = goal.target_minor - progress
    if remaining <= 0:
        return today
    # Trailing-90-day net contribution rate on linked account, or
    # sum of contributions in last 90 days if contribution_tagged.
    start = dt.datetime.combine(today - dt.timedelta(days=90), dt.time.min)
    if goal.progress_mode == "account_linked" and goal.account_id:
        rows = (await session.execute(
            select(Transaction).where(
                Transaction.account_id == goal.account_id,
                Transaction.deleted_at.is_(None),
                Transaction.occurred_at >= start,
            )
        )).scalars().all()
        net = 0
        for t in rows:
            if t.kind in ("income", "transfer_in"):
                net += t.amount_minor
            elif t.kind in ("expense", "transfer_out"):
                net -= t.amount_minor
    else:
        rows = (await session.execute(
            select(GoalContribution).join(Transaction, Transaction.id == GoalContribution.transaction_id)
            .where(GoalContribution.goal_id == goal.id, Transaction.occurred_at >= start)
        )).scalars().all()
        net = sum(c.amount_minor for c in rows)
    if net <= 0:
        return None
    daily = net / 90.0
    days = remaining / daily
    return today + dt.timedelta(days=int(days))

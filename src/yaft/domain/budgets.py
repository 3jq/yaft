from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yaft.db.models import AlertFired, Budget, Category, Transaction


def month_window(d: dt.date) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime(d.year, d.month, 1)
    if d.month == 12:
        end = dt.datetime(d.year + 1, 1, 1)
    else:
        end = dt.datetime(d.year, d.month + 1, 1)
    return start, end


def period_key(d: dt.date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


async def _descendants(session: AsyncSession, root: int) -> set[int]:
    out = {root}
    cats = (await session.execute(select(Category))).scalars().all()
    by_parent: dict[int | None, list[int]] = {}
    for c in cats:
        by_parent.setdefault(c.parent_id, []).append(c.id)
    stack = [root]
    while stack:
        cur = stack.pop()
        for child in by_parent.get(cur, []):
            if child not in out:
                out.add(child)
                stack.append(child)
    return out


async def spent_minor(session: AsyncSession, *, category_id: int, on: dt.date) -> int:
    ids = await _descendants(session, category_id)
    start, end = month_window(on)
    rows = (await session.execute(
        select(Transaction).where(
            Transaction.deleted_at.is_(None),
            Transaction.kind == "expense",
            Transaction.occurred_at >= start,
            Transaction.occurred_at < end,
            Transaction.category_id.in_(ids),
        )
    )).scalars().all()
    return sum(r.base_amount_minor for r in rows)


@dataclass
class DueAlert:
    budget_id: int
    category_id: int
    threshold: float
    spent_minor: int
    budget_minor: int


async def due_alerts(session: AsyncSession, today: dt.date) -> list[DueAlert]:
    pkey = period_key(today)
    fired = {(a.category_id, a.threshold) for a in
             (await session.execute(select(AlertFired).where(AlertFired.period_key == pkey)))
             .scalars().all()}
    out: list[DueAlert] = []
    for b in (await session.execute(select(Budget))).scalars().all():
        thresholds: list[float] = json.loads(b.alert_thresholds)
        s = await spent_minor(session, category_id=b.category_id, on=today)
        if b.amount_minor <= 0:
            continue
        frac = s / b.amount_minor
        for t in thresholds:
            if frac >= t and (b.category_id, t) not in fired:
                out.append(DueAlert(b.id, b.category_id, t, s, b.amount_minor))
    return out


async def mark_fired(session: AsyncSession, budget_id: int, today: dt.date, threshold: float) -> None:
    b = await session.get(Budget, budget_id)
    if not b:
        return
    session.add(AlertFired(category_id=b.category_id, period_key=period_key(today), threshold=threshold))

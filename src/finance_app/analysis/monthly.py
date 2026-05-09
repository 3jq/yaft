from __future__ import annotations

import datetime as dt
import statistics

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.db.models import Category, Setting, Transaction


def _bounds(year: int, month: int) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime(year, month, 1)
    if month == 12:
        end = dt.datetime(year + 1, 1, 1)
    else:
        end = dt.datetime(year, month + 1, 1)
    return start, end


def _prev_month(year: int, month: int, k: int) -> tuple[int, int]:
    m = (year * 12 + (month - 1)) - k
    return m // 12, (m % 12) + 1


async def aggregate_monthly(session: AsyncSession, today: dt.date) -> dict:
    # "Last full month" = the month ending before today's month start.
    y, m = _prev_month(today.year, today.month, 1)
    last_start, last_end = _bounds(y, m)
    py, pm = _prev_month(today.year, today.month, 2)
    prev_start, prev_end = _bounds(py, pm)

    rows = (
        await session.execute(
            select(Transaction).where(
                Transaction.deleted_at.is_(None),
                Transaction.occurred_at >= prev_start,
                Transaction.occurred_at < last_end,
            )
        )
    ).scalars().all()
    last = [t for t in rows if last_start <= t.occurred_at < last_end]
    prev = [t for t in rows if prev_start <= t.occurred_at < prev_end]
    last_total = sum(t.base_amount_minor for t in last if t.kind == "expense")
    prev_total = sum(t.base_amount_minor for t in prev if t.kind == "expense")

    # Top-level category aggregation last month
    cats = (await session.execute(select(Category))).scalars().all()
    parent_of = {c.id: c.parent_id for c in cats}
    name_of = {c.id: c.name for c in cats}

    def root(cid):
        while parent_of.get(cid):
            cid = parent_of[cid]
        return cid

    by_root: dict[int, int] = {}
    for t in last:
        if t.kind == "expense" and t.category_id:
            r = root(t.category_id)
            by_root[r] = by_root.get(r, 0) + t.base_amount_minor

    # Trailing-3-month average per root
    threem_start, _ = _bounds(*_prev_month(today.year, today.month, 3))
    rows3 = (
        await session.execute(
            select(Transaction).where(
                Transaction.deleted_at.is_(None),
                Transaction.occurred_at >= threem_start,
                Transaction.occurred_at < last_end,
                Transaction.kind == "expense",
            )
        )
    ).scalars().all()

    by_root_3m_per_month: dict[int, list[int]] = {}
    months = []
    for k in (3, 2, 1):
        ys, ms = _prev_month(today.year, today.month, k)
        months.append((ys, ms, _bounds(ys, ms)))
    for _ys, _ms, (ws, we) in months:
        for r in set(parent_of.values()) | set(by_root):
            if r is None:
                continue
            total = sum(
                t.base_amount_minor
                for t in rows3
                if ws <= t.occurred_at < we and t.category_id and root(t.category_id) == r
            )
            by_root_3m_per_month.setdefault(r, []).append(total)
    avg_by_root = {
        r: int(statistics.mean(v) if v else 0)
        for r, v in by_root_3m_per_month.items()
    }

    base_row = (
        await session.execute(select(Setting).where(Setting.key == "base_currency"))
    ).scalar_one_or_none()
    base = base_row.value if base_row else "USD"

    return {
        "month_label": f"{y:04d}-{m:02d}",
        "base_currency": base,
        "last_total_minor": last_total,
        "prev_total_minor": prev_total,
        "delta_pct": (
            (last_total - prev_total) / prev_total * 100 if prev_total else None
        ),
        "by_root": [
            {
                "root_id": r,
                "name": name_of.get(r, "?"),
                "last_minor": amt,
                "avg_3m_minor": avg_by_root.get(r, 0),
                "delta_vs_avg_pct": (
                    (amt - avg_by_root.get(r, 0)) / avg_by_root[r] * 100
                    if avg_by_root.get(r)
                    else None
                ),
            }
            for r, amt in sorted(by_root.items(), key=lambda kv: -kv[1])
        ],
    }


async def write_summary_narrative(llm, agg: dict) -> str:
    prompt = (
        "You are a friendly personal-finance reporter. Produce 5 bullet points (no preamble)"
        f" summarizing month {agg['month_label']} ({agg['base_currency']} totals; cents)."
        " Cover: total spent vs prior month, biggest categories, biggest movers vs 3-month"
        " average, anomalies, one suggestion. Be specific with numbers (convert cents to"
        f" dollars). Data:\n{agg}"
    )
    resp = await llm._sdk.chat.completions.create(
        model=llm._parse_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return resp.choices[0].message.content or ""

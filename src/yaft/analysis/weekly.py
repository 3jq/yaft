from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yaft.db.models import Account, Budget, Category, Goal, Setting, Transaction
from yaft.domain.budgets import spent_minor
from yaft.domain.goals import progress_minor, projected_hit_date


async def gather(session: AsyncSession, today: dt.date) -> dict:
    base_row = (
        await session.execute(select(Setting).where(Setting.key == "base_currency"))
    ).scalar_one_or_none()
    base = base_row.value if base_row else "USD"

    cats = {c.id: c for c in (await session.execute(select(Category))).scalars().all()}

    def root(cid: int) -> int:
        while cats[cid].parent_id:
            cid = cats[cid].parent_id
        return cid

    async def _rolling(days: int) -> dict[int, int]:
        start = dt.datetime.combine(today - dt.timedelta(days=days), dt.time.min)
        rows = (
            await session.execute(
                select(Transaction).where(
                    Transaction.deleted_at.is_(None),
                    Transaction.kind == "expense",
                    Transaction.occurred_at >= start,
                )
            )
        ).scalars().all()
        out: dict[int, int] = {}
        for t in rows:
            if not t.category_id:
                continue
            r = root(t.category_id)
            out[r] = out.get(r, 0) + t.base_amount_minor
        return out

    last30 = await _rolling(30)
    last90 = await _rolling(90)

    budgets = []
    for b in (await session.execute(select(Budget))).scalars().all():
        if b.category_id not in cats:
            continue
        spent = await spent_minor(session, category_id=b.category_id, on=today)
        budgets.append({
            "category_id": b.category_id,
            "name": cats[b.category_id].name,
            "amount_minor": b.amount_minor,
            "spent_minor": spent,
            "fraction": spent / b.amount_minor if b.amount_minor else 0.0,
        })

    goals = []
    for g in (await session.execute(select(Goal).where(Goal.archived == 0))).scalars().all():
        prog = await progress_minor(session, g)
        eta = await projected_hit_date(session, g, today)
        goals.append({
            "name": g.name,
            "progress_minor": prog,
            "target_minor": g.target_minor,
            "currency": g.currency,
            "projected_hit_date": eta.isoformat() if eta else None,
        })

    accs = []
    for a in (
        await session.execute(select(Account).where(Account.archived == 0))
    ).scalars().all():
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
        accs.append({"name": a.name, "currency": a.currency, "balance_minor": bal})

    return {
        "base_currency": base,
        "today": today.isoformat(),
        "last30_by_root": [
            {"root_id": k, "name": cats[k].name, "minor": v}
            for k, v in last30.items()
        ],
        "last90_by_root": [
            {"root_id": k, "name": cats[k].name, "minor": v}
            for k, v in last90.items()
        ],
        "budgets": budgets,
        "goals": goals,
        "accounts": accs,
    }


async def coach_narrative(llm, snapshot: dict) -> str:
    prompt = (
        "You are a frank but kind savings coach. Write a short weekly digest:\n"
        "1) one sentence on overall trajectory; 2) 1-2 specific savings suggestions tied"
        " to the data (name a category and an approximate dollar saving); 3) one line per"
        " goal with progress and ETA. No markdown headers; bullets are fine. Money is"
        " integer cents — convert to dollars.\n\n"
        f"Snapshot:\n{json.dumps(snapshot, default=str)}"
    )
    resp = await llm._sdk.chat.completions.create(
        model=llm._parse_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""

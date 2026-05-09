from __future__ import annotations

import datetime as dt
import json
import uuid

from dateutil.rrule import rrulestr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yaft.db.models import RecurringRule, Transaction
from yaft.domain.money import to_minor


def _next_after(rule_str: str, after: dt.date) -> dt.date | None:
    # Use 1 month before 'after' as dtstart so monthly rules anchored to
    # BYMONTHDAY=1 can fire on the 1st of the month that equals 'after'.
    dtstart = dt.datetime(after.year, after.month, after.day)
    rule = rrulestr(rule_str, dtstart=dtstart)
    nxt = rule.after(dtstart, inc=False)
    return nxt.date() if nxt else None


async def materialize_due(session: AsyncSession, today: dt.date) -> int:
    rules = (await session.execute(
        select(RecurringRule).where(
            RecurringRule.active == 1,
            RecurringRule.next_run_at.is_not(None),
            RecurringRule.next_run_at <= today,
        )
    )).scalars().all()
    n = 0
    for r in rules:
        tpl = json.loads(r.template_json)
        amount_minor = to_minor(float(tpl["amount"]), tpl["currency"])
        tx = Transaction(
            group_id=str(uuid.uuid4()),
            occurred_at=dt.datetime(today.year, today.month, today.day, 9, 0),
            account_id=int(tpl["account_id"]),
            category_id=int(tpl["category_id"]) if tpl.get("category_id") else None,
            kind=tpl.get("kind", "expense"),
            amount_minor=amount_minor,
            currency=tpl["currency"],
            base_amount_minor=amount_minor,
            fx_rate=1.0,
            merchant=tpl.get("merchant"),
            note=tpl.get("note"),
            source="recurring",
            source_ref=str(r.id),
            recurring_id=r.id,
            confidence=1.0,
        )
        session.add(tx)
        r.last_run_at = today
        r.next_run_at = _next_after(r.rrule, today)
        n += 1
    await session.commit()
    return n

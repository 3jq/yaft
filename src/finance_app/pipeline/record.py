from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.db.models import Transaction
from finance_app.pipeline.resolver import ResolvedTransaction


async def record(
    session: AsyncSession,
    r: ResolvedTransaction,
    *,
    source: str,
    source_ref: str | None = None,
    raw_input: str | None = None,
) -> Transaction:
    tx = Transaction(
        group_id=str(uuid.uuid4()),
        occurred_at=r.occurred_at,
        account_id=r.account_id,
        category_id=r.category_id,
        kind=r.kind,
        amount_minor=r.amount_minor,
        currency=r.currency,
        base_amount_minor=r.base_amount_minor,
        fx_rate=r.fx_rate,
        merchant=r.merchant,
        note=r.note,
        source=source,
        source_ref=source_ref,
        raw_input=raw_input,
        confidence=r.confidence,
    )
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx

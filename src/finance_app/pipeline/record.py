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
    group_id = str(uuid.uuid4())

    # Transfers: two legs sharing group_id
    if r.kind == "transfer":
        if r.transfer_to_account_id is None:
            raise ValueError("transfer requires transfer_to_account_id")
        out_leg = Transaction(
            group_id=group_id, occurred_at=r.occurred_at,
            account_id=r.account_id, category_id=None, kind="transfer_out",
            amount_minor=r.amount_minor, currency=r.currency,
            base_amount_minor=r.base_amount_minor, fx_rate=r.fx_rate,
            note=r.note, source=source, source_ref=source_ref, raw_input=raw_input,
            confidence=r.confidence,
        )
        in_leg = Transaction(
            group_id=group_id, occurred_at=r.occurred_at,
            account_id=r.transfer_to_account_id, category_id=None, kind="transfer_in",
            amount_minor=r.amount_minor, currency=r.currency,
            base_amount_minor=r.base_amount_minor, fx_rate=r.fx_rate,
            note=r.note, source=source, source_ref=source_ref, raw_input=raw_input,
            confidence=r.confidence,
        )
        session.add_all([out_leg, in_leg])
        await session.commit()
        await session.refresh(out_leg)
        return out_leg

    # Splits: N legs on the same account
    if r.splits:
        legs: list[Transaction] = []
        for s in r.splits:
            base_minor = round(r.base_amount_minor * (s["amount_minor"] / r.amount_minor))
            legs.append(Transaction(
                group_id=group_id, occurred_at=r.occurred_at,
                account_id=r.account_id, category_id=s["category_id"], kind=r.kind,
                amount_minor=s["amount_minor"], currency=r.currency,
                base_amount_minor=base_minor, fx_rate=r.fx_rate,
                merchant=r.merchant, note=s.get("note") or r.note,
                source=source, source_ref=source_ref, raw_input=raw_input,
                confidence=r.confidence,
            ))
        session.add_all(legs)
        await session.commit()
        await session.refresh(legs[0])
        return legs[0]

    # Single leg
    tx = Transaction(
        group_id=group_id, occurred_at=r.occurred_at,
        account_id=r.account_id, category_id=r.category_id, kind=r.kind,
        amount_minor=r.amount_minor, currency=r.currency,
        base_amount_minor=r.base_amount_minor, fx_rate=r.fx_rate,
        merchant=r.merchant, note=r.note,
        source=source, source_ref=source_ref, raw_input=raw_input,
        confidence=r.confidence,
    )
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx

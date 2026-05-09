from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from finance_app.api.auth import require_owner
from finance_app.api.schemas import SplitRequest, TransactionOut, TransactionPatch
from finance_app.db.models import Transaction

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


async def _session(request: Request) -> AsyncSession:
    Session: async_sessionmaker = request.app.state.session_maker
    async with Session() as s:
        yield s


@router.get("", response_model=list[TransactionOut])
async def list_tx(
    include_deleted: bool = False,
    limit: int = Query(default=200, le=1000),
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    q = select(Transaction).order_by(desc(Transaction.occurred_at)).limit(limit)
    if not include_deleted:
        q = q.where(Transaction.deleted_at.is_(None))
    rows = (await session.execute(q)).scalars().all()
    return [TransactionOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/{tx_id}", response_model=TransactionOut)
async def get_tx(
    tx_id: int,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    tx = await session.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "not found")
    return TransactionOut.model_validate(tx, from_attributes=True)


@router.patch("/{tx_id}", response_model=TransactionOut)
async def patch_tx(
    tx_id: int,
    body: TransactionPatch,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    tx = await session.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(tx, k, v)
    tx.updated_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    await session.commit()
    await session.refresh(tx)
    return TransactionOut.model_validate(tx, from_attributes=True)


@router.delete("/{tx_id}", status_code=204)
async def delete_tx(
    tx_id: int,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    tx = await session.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "not found")
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    tx.deleted_at = now
    tx.updated_at = now
    await session.commit()
    return Response(status_code=204)


@router.post("/{tx_id}/restore", status_code=204)
async def restore_tx(
    tx_id: int,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    tx = await session.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "not found")
    tx.deleted_at = None
    tx.updated_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    await session.commit()
    return Response(status_code=204)


@router.post("/{tx_id}/split", response_model=list[TransactionOut])
async def split_tx(
    tx_id: int,
    body: SplitRequest,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    tx = await session.get(Transaction, tx_id)
    if not tx or tx.deleted_at:
        raise HTTPException(404, "not found")
    total = sum(s.amount_minor for s in body.splits)
    if total != tx.amount_minor:
        raise HTTPException(400, f"splits sum {total} != original {tx.amount_minor}")
    if tx.kind not in ("expense", "income"):
        raise HTTPException(400, "only expense/income can be split")
    group_id = tx.group_id or str(uuid.uuid4())
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    tx.deleted_at = now
    tx.updated_at = now
    legs: list[Transaction] = []
    for s in body.splits:
        base_minor = round(tx.base_amount_minor * (s.amount_minor / tx.amount_minor))
        legs.append(Transaction(
            group_id=group_id,
            occurred_at=tx.occurred_at,
            account_id=tx.account_id,
            category_id=s.category_id,
            kind=tx.kind,
            amount_minor=s.amount_minor,
            currency=tx.currency,
            base_amount_minor=base_minor,
            fx_rate=tx.fx_rate,
            merchant=tx.merchant,
            note=s.note or tx.note,
            source="split",
            source_ref=str(tx.id),
            confidence=tx.confidence,
        ))
    session.add_all(legs)
    await session.commit()
    for leg in legs:
        await session.refresh(leg)
    return [TransactionOut.model_validate(leg, from_attributes=True) for leg in legs]

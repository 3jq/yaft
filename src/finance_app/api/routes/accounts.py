from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.api.auth import require_owner
from finance_app.api.routes.transactions import _session
from finance_app.api.schemas import AccountIn, AccountOut
from finance_app.db.models import Account

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
async def list_accounts(
    include_archived: bool = False,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    q = select(Account)
    if not include_archived:
        q = q.where(Account.archived == 0)
    rows = (await session.execute(q.order_by(Account.id))).scalars().all()
    return [AccountOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("", response_model=AccountOut, status_code=201)
async def create_account(
    body: AccountIn,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    a = Account(
        name=body.name,
        kind=body.kind,
        currency=body.currency.upper(),
        opening_balance_minor=body.opening_balance_minor,
    )
    session.add(a)
    try:
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(400, "name must be unique") from e
    await session.refresh(a)
    return AccountOut.model_validate(a, from_attributes=True)


@router.patch("/{aid}", response_model=AccountOut)
async def patch_account(
    aid: int,
    body: AccountIn,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    a = await session.get(Account, aid)
    if not a:
        raise HTTPException(404, "not found")
    a.name = body.name
    a.kind = body.kind
    a.currency = body.currency.upper()
    a.opening_balance_minor = body.opening_balance_minor
    await session.commit()
    await session.refresh(a)
    return AccountOut.model_validate(a, from_attributes=True)


@router.post("/{aid}/archive", status_code=204)
async def archive_account(
    aid: int,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    a = await session.get(Account, aid)
    if not a:
        raise HTTPException(404, "not found")
    a.archived = 1
    await session.commit()
    return Response(status_code=204)

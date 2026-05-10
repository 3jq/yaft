from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yaft.api.auth import require_owner
from yaft.api.routes.transactions import _session
from yaft.api.schemas import AccountIn, AccountOut
from yaft.db.models import Account, Goal, Transaction

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/balances_series")
async def balances_series(
    days: int = 30,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    """Per-account end-of-day balance points (in the account's own currency)
    for the last N days. Used by the Home page per-account sparklines."""
    import datetime as dt

    today = dt.date.today()
    days = max(2, min(days, 365))
    start_day = today - dt.timedelta(days=days - 1)

    accs = (
        await session.execute(select(Account).where(Account.archived == 0))
    ).scalars().all()

    out = []
    for a in accs:
        rows = (
            await session.execute(
                select(Transaction)
                .where(
                    Transaction.account_id == a.id,
                    Transaction.deleted_at.is_(None),
                )
                .order_by(Transaction.occurred_at)
            )
        ).scalars().all()

        end_of_day: dict[dt.date, int] = {}
        running = a.opening_balance_minor
        for t in rows:
            if t.kind in ("income", "transfer_in"):
                running += t.amount_minor
            elif t.kind in ("expense", "transfer_out"):
                running -= t.amount_minor
            end_of_day[t.occurred_at.date()] = running

        sorted_days = sorted(end_of_day.keys())
        cur = a.opening_balance_minor
        j = 0
        for d in sorted_days:
            if d < start_day:
                cur = end_of_day[d]
                j += 1
            else:
                break

        points = []
        for i in range(days):
            d = start_day + dt.timedelta(days=i)
            while j < len(sorted_days) and sorted_days[j] <= d:
                cur = end_of_day[sorted_days[j]]
                j += 1
            points.append({"date": d.isoformat(), "value_minor": cur})

        out.append({
            "account_id": a.id,
            "currency": a.currency,
            "points": points,
        })

    return {"accounts": out}


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


@router.delete("/{aid}", status_code=204)
async def delete_account(
    aid: int,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    a = await session.get(Account, aid)
    if not a:
        raise HTTPException(404, "not found")

    tx_count = (
        await session.execute(
            select(Transaction).where(Transaction.account_id == aid).limit(1)
        )
    ).first()
    if tx_count is not None:
        raise HTTPException(
            409, "account has transactions; archive instead of deleting"
        )

    goal_ref = (
        await session.execute(select(Goal).where(Goal.account_id == aid).limit(1))
    ).first()
    if goal_ref is not None:
        raise HTTPException(409, "account is linked to a goal")

    await session.delete(a)
    await session.commit()
    return Response(status_code=204)

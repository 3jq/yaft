from __future__ import annotations

import datetime as dt
import json

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yaft.api.auth import require_owner
from yaft.api.routes.transactions import _session
from yaft.db.models import Budget
from yaft.domain.budgets import spent_minor


class BudgetIn(BaseModel):
    category_id: int
    amount_minor: int = Field(gt=0)
    currency: str
    alert_thresholds: list[float] = Field(default_factory=lambda: [0.8, 1.0])
    starts_on: dt.date | None = None
    ends_on: dt.date | None = None


class BudgetOut(BaseModel):
    id: int
    category_id: int
    amount_minor: int
    currency: str
    alert_thresholds: list[float]
    starts_on: dt.date | None = None
    ends_on: dt.date | None = None


router = APIRouter(prefix="/api/budgets", tags=["budgets"])


def _budget_out(b: Budget) -> BudgetOut:
    return BudgetOut(
        id=b.id,
        category_id=b.category_id,
        amount_minor=b.amount_minor,
        currency=b.currency,
        alert_thresholds=json.loads(b.alert_thresholds),
        starts_on=b.starts_on,
        ends_on=b.ends_on,
    )


@router.get("", response_model=list[BudgetOut])
async def list_budgets(
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    rows = (await session.execute(select(Budget))).scalars().all()
    return [_budget_out(b) for b in rows]


@router.post("", response_model=BudgetOut, status_code=201)
async def create_budget(
    body: BudgetIn,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    b = Budget(
        category_id=body.category_id,
        amount_minor=body.amount_minor,
        currency=body.currency.upper(),
        alert_thresholds=json.dumps(body.alert_thresholds),
        starts_on=body.starts_on,
        ends_on=body.ends_on,
    )
    session.add(b)
    await session.commit()
    await session.refresh(b)
    return _budget_out(b)


@router.delete("/{bid}", status_code=204)
async def delete_budget(
    bid: int,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    b = await session.get(Budget, bid)
    if not b:
        raise HTTPException(404, "not found")
    await session.delete(b)
    await session.commit()
    return Response(status_code=204)


@router.get("/progress")
async def progress(
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    today = dt.date.today()
    out = []
    for b in (await session.execute(select(Budget))).scalars().all():
        spent = await spent_minor(session, category_id=b.category_id, on=today)
        out.append(
            {
                "budget_id": b.id,
                "category_id": b.category_id,
                "amount_minor": b.amount_minor,
                "spent_minor": spent,
                "currency": b.currency,
                "fraction": (spent / b.amount_minor) if b.amount_minor else 0.0,
            }
        )
    return out

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.api.auth import require_owner
from finance_app.api.routes.transactions import _session
from finance_app.db.models import Goal
from finance_app.domain.goals import progress_minor, projected_hit_date


class GoalIn(BaseModel):
    name: str
    target_minor: int
    currency: str
    progress_mode: str  # account_linked | contribution_tagged
    account_id: int | None = None
    target_date: dt.date | None = None


class GoalOut(BaseModel):
    id: int
    name: str
    target_minor: int
    currency: str
    progress_mode: str
    account_id: int | None = None
    target_date: dt.date | None = None


router = APIRouter(prefix="/api/goals", tags=["goals"])


def _goal_out(g: Goal) -> GoalOut:
    return GoalOut(
        id=g.id,
        name=g.name,
        target_minor=g.target_minor,
        currency=g.currency,
        progress_mode=g.progress_mode,
        account_id=g.account_id,
        target_date=g.target_date,
    )


@router.get("", response_model=list[GoalOut])
async def list_goals(
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    rows = (await session.execute(select(Goal).where(Goal.archived == 0))).scalars().all()
    return [_goal_out(g) for g in rows]


@router.post("", response_model=GoalOut, status_code=201)
async def create_goal(
    body: GoalIn,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    g = Goal(
        name=body.name,
        target_minor=body.target_minor,
        currency=body.currency.upper(),
        progress_mode=body.progress_mode,
        account_id=body.account_id,
        target_date=body.target_date,
    )
    session.add(g)
    await session.commit()
    await session.refresh(g)
    return _goal_out(g)


@router.post("/{gid}/archive", status_code=204)
async def archive_goal(
    gid: int,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    g = await session.get(Goal, gid)
    if not g:
        raise HTTPException(404, "not found")
    g.archived = 1
    await session.commit()
    return Response(status_code=204)


@router.get("/progress")
async def progress(
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    today = dt.date.today()
    out = []
    for g in (await session.execute(select(Goal).where(Goal.archived == 0))).scalars().all():
        prog = await progress_minor(session, g)
        eta = await projected_hit_date(session, g, today)
        out.append(
            {
                "id": g.id,
                "name": g.name,
                "target_minor": g.target_minor,
                "currency": g.currency,
                "progress_minor": prog,
                "fraction": prog / g.target_minor if g.target_minor else 0.0,
                "projected_hit_date": eta.isoformat() if eta else None,
                "target_date": g.target_date.isoformat() if g.target_date else None,
            }
        )
    return out

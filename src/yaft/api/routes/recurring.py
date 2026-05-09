from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yaft.api.auth import require_owner
from yaft.api.routes.transactions import _session
from yaft.db.models import RecurringRule


class RecurringIn(BaseModel):
    name: str
    rrule: str
    template_json: str  # raw JSON string
    next_run_at: dt.date | None = None


class RecurringOut(BaseModel):
    id: int
    name: str
    rrule: str
    template_json: str
    next_run_at: dt.date | None = None
    last_run_at: dt.date | None = None
    active: int = 1


router = APIRouter(prefix="/api/recurring", tags=["recurring"])


def _rule_out(r: RecurringRule) -> RecurringOut:
    return RecurringOut(
        id=r.id,
        name=r.name,
        rrule=r.rrule,
        template_json=r.template_json,
        next_run_at=r.next_run_at,
        last_run_at=r.last_run_at,
        active=r.active,
    )


@router.get("", response_model=list[RecurringOut])
async def list_rules(
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    rows = (await session.execute(select(RecurringRule))).scalars().all()
    return [_rule_out(r) for r in rows]


@router.post("", response_model=RecurringOut, status_code=201)
async def create_rule(
    body: RecurringIn,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    r = RecurringRule(
        name=body.name,
        rrule=body.rrule,
        template_json=body.template_json,
        next_run_at=body.next_run_at,
        active=1,
    )
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return _rule_out(r)


@router.post("/{rid}/pause", status_code=204)
async def pause_rule(
    rid: int,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    r = await session.get(RecurringRule, rid)
    if not r:
        raise HTTPException(404, "not found")
    r.active = 0
    await session.commit()
    return Response(status_code=204)


@router.post("/{rid}/resume", status_code=204)
async def resume_rule(
    rid: int,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    r = await session.get(RecurringRule, rid)
    if not r:
        raise HTTPException(404, "not found")
    r.active = 1
    await session.commit()
    return Response(status_code=204)


@router.delete("/{rid}", status_code=204)
async def delete_rule(
    rid: int,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    r = await session.get(RecurringRule, rid)
    if not r:
        raise HTTPException(404, "not found")
    await session.delete(r)
    await session.commit()
    return Response(status_code=204)

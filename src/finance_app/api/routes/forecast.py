from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.analysis.forecast import forecast as compute
from finance_app.api.auth import require_owner
from finance_app.api.routes.transactions import _session

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.get("")
async def get_forecast(
    session: AsyncSession = Depends(_session),
    _u=Depends(require_owner),
):
    return await compute(session, today=dt.date.today())

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from yaft.analysis.forecast import forecast as compute
from yaft.api.auth import require_owner
from yaft.api.routes.transactions import _session

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.get("")
async def get_forecast(
    session: AsyncSession = Depends(_session),
    _u=Depends(require_owner),
):
    return await compute(session, today=dt.date.today())

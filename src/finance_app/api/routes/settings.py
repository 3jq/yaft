from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.api.auth import require_owner
from finance_app.api.routes.transactions import _session
from finance_app.api.schemas import SettingsOut, SettingsPatch
from finance_app.db.models import Setting

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULTS = {
    "base_currency": "USD",
    "timezone": "UTC",
    "default_account_id": "1",
    "alert_thresholds_default": "[0.8,1.0]",
}


async def _read(session: AsyncSession) -> SettingsOut:
    rows = {
        r.key: r.value
        for r in (await session.execute(select(Setting))).scalars().all()
    }
    out = {**DEFAULTS, **rows}
    return SettingsOut(
        base_currency=out["base_currency"],
        timezone=out["timezone"],
        default_account_id=int(out["default_account_id"]),
        alert_thresholds_default=json.loads(out["alert_thresholds_default"]),
    )


async def _set(session: AsyncSession, key: str, value: str) -> None:
    row = (
        await session.execute(select(Setting).where(Setting.key == key))
    ).scalar_one_or_none()
    if row:
        row.value = value
    else:
        session.add(Setting(key=key, value=value))


@router.get("", response_model=SettingsOut)
async def get_settings_route(
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    return await _read(session)


@router.patch("", response_model=SettingsOut)
async def patch_settings_route(
    body: SettingsPatch,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    if body.base_currency is not None:
        await _set(session, "base_currency", body.base_currency)
    if body.timezone is not None:
        await _set(session, "timezone", body.timezone)
    if body.default_account_id is not None:
        await _set(session, "default_account_id", str(body.default_account_id))
    if body.alert_thresholds_default is not None:
        await _set(session, "alert_thresholds_default", json.dumps(body.alert_thresholds_default))
    await session.commit()
    return await _read(session)

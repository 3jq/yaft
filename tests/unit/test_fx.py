import datetime as dt

import httpx
import pytest
import respx
from sqlalchemy import select

from finance_app.db.models import FxRate
from finance_app.domain.fx import FxService


@pytest.fixture
async def fx(session):
    return FxService(session, http_client=httpx.AsyncClient())

@respx.mock
async def test_fetch_then_cache(fx, session):
    today = dt.date(2026, 5, 9)
    respx.get("https://api.exchangerate.host/2026-05-09").mock(
        return_value=httpx.Response(200, json={"base": "USD", "rates": {"EUR": 0.92, "AED": 3.67}})
    )
    rate = await fx.get_rate(today, "USD", "EUR")
    assert abs(rate - 0.92) < 1e-9
    rows = (await session.execute(select(FxRate))).scalars().all()
    assert len(rows) == 2  # both EUR and AED cached

    rate2 = await fx.get_rate(today, "USD", "EUR")
    assert rate2 == rate

async def test_same_currency_returns_one(fx):
    assert await fx.get_rate(dt.date(2026, 5, 9), "USD", "USD") == 1.0

@respx.mock
async def test_fallback_to_previous_cached_on_api_failure(fx, session):
    session.add(FxRate(date=dt.date(2026, 5, 8), base="USD", quote="EUR", rate=0.91))
    await session.commit()
    respx.get("https://api.exchangerate.host/2026-05-09").mock(
        return_value=httpx.Response(500))
    rate = await fx.get_rate(dt.date(2026, 5, 9), "USD", "EUR")
    assert rate == 0.91

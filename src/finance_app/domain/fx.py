from __future__ import annotations

import datetime as dt

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.db.models import FxRate

API = "https://api.exchangerate.host"

class FxService:
    def __init__(self, session: AsyncSession, *, http_client: httpx.AsyncClient | None = None):
        self.s = session
        self.http = http_client or httpx.AsyncClient(timeout=10.0)

    async def get_rate(self, on: dt.date, base: str, quote: str) -> float:
        base, quote = base.upper(), quote.upper()
        if base == quote:
            return 1.0
        # cache hit on exact date
        row = (await self.s.execute(
            select(FxRate).where(FxRate.date == on, FxRate.base == base, FxRate.quote == quote)
        )).scalar_one_or_none()
        if row:
            return row.rate
        # miss → fetch
        try:
            r = await self.http.get(f"{API}/{on.isoformat()}", params={"base": base})
            r.raise_for_status()
            data = r.json()
            rates = data.get("rates") or {}
            for q, v in rates.items():
                self.s.add(FxRate(date=on, base=base, quote=q, rate=float(v)))
            await self.s.commit()
            if quote in rates:
                return float(rates[quote])
        except Exception:
            pass
        # fallback: most recent cached rate for this pair
        prev = (await self.s.execute(
            select(FxRate).where(FxRate.base == base, FxRate.quote == quote)
            .order_by(desc(FxRate.date)).limit(1)
        )).scalar_one_or_none()
        if prev:
            return prev.rate
        raise RuntimeError(f"no FX rate available for {base}->{quote} on {on}")

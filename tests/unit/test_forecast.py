import datetime as dt

import pytest

from finance_app.analysis.forecast import forecast
from finance_app.db.models import Account, Currency, Goal, Setting, Transaction


@pytest.fixture
async def seeded(session):
    session.add_all([
        Currency(code="USD", name="USD"),
        Account(id=1, name="Cash", kind="cash", currency="USD", opening_balance_minor=100000),
        Setting(key="base_currency", value="USD"),
    ])
    today = dt.date.today()
    # 90 days of -1000/day expenses
    for d in range(90):
        when = dt.datetime.combine(today - dt.timedelta(days=d), dt.time(12, 0))
        session.add(Transaction(
            group_id=f"g{d}",
            occurred_at=when,
            account_id=1,
            kind="expense",
            amount_minor=1000,
            currency="USD",
            base_amount_minor=1000,
            fx_rate=1.0,
        ))
    await session.commit()
    return session


async def test_forecast_emits_runway(seeded):
    f = await forecast(seeded, today=dt.date.today())
    assert f["runway_months"] is not None
    assert f["eom_net_minor"] < 0  # all expenses, no income

import datetime as dt

import pytest

from yaft.analysis.monthly import aggregate_monthly
from yaft.db.models import Account, Category, Currency, Setting, Transaction


@pytest.fixture
async def seeded(session):
    session.add_all([
        Currency(code="USD", name="USD"),
        Account(id=1, name="Cash", kind="cash", currency="USD"),
        Category(id=1, name="Food", kind="expense"),
        Setting(key="base_currency", value="USD"),
    ])
    # last month (April 2026): 100 + 200 = 300
    last = dt.datetime(2026, 4, 15)
    # prev month (March 2026): 150
    prev = dt.datetime(2026, 3, 10)
    session.add_all([
        Transaction(
            group_id="a", occurred_at=last, account_id=1, category_id=1,
            kind="expense", amount_minor=10000, currency="USD",
            base_amount_minor=10000, fx_rate=1.0,
        ),
        Transaction(
            group_id="b", occurred_at=last, account_id=1, category_id=1,
            kind="expense", amount_minor=20000, currency="USD",
            base_amount_minor=20000, fx_rate=1.0,
        ),
        Transaction(
            group_id="c", occurred_at=prev, account_id=1, category_id=1,
            kind="expense", amount_minor=15000, currency="USD",
            base_amount_minor=15000, fx_rate=1.0,
        ),
    ])
    await session.commit()
    return session


async def test_aggregate_monthly_basic(seeded):
    agg = await aggregate_monthly(seeded, today=dt.date(2026, 5, 9))
    assert agg["month_label"] == "2026-04"
    assert agg["last_total_minor"] == 30000
    assert agg["prev_total_minor"] == 15000

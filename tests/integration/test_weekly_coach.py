import datetime as dt

import pytest

from finance_app.analysis.weekly import gather
from finance_app.db.models import Account, Category, Currency, Setting, Transaction


@pytest.fixture
async def seeded(session):
    session.add_all([
        Currency(code="USD", name="USD"),
        Account(id=1, name="Cash", kind="cash", currency="USD"),
        Category(id=1, name="Food", kind="expense"),
        Setting(key="base_currency", value="USD"),
        Transaction(
            group_id="g",
            occurred_at=dt.datetime.now(),
            account_id=1,
            category_id=1,
            kind="expense",
            amount_minor=1500,
            currency="USD",
            base_amount_minor=1500,
            fx_rate=1.0,
        ),
    ])
    await session.commit()
    return session


async def test_gather_returns_snapshot(seeded):
    snap = await gather(seeded, today=dt.date.today())
    assert snap["base_currency"] == "USD"
    assert any(x["minor"] == 1500 for x in snap["last30_by_root"])

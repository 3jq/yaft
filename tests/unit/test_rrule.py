import datetime as dt
import json
import pytest
from sqlalchemy import select
from yaft.domain.rrule import materialize_due
from yaft.db.models import Account, Category, Currency, RecurringRule, Setting, Transaction


@pytest.fixture
async def seeded(session):
    session.add_all([
        Currency(code="USD", name="USD"),
        Account(id=1, name="Bank", kind="bank", currency="USD"),
        Category(id=1, name="Subscriptions", kind="expense"),
        Setting(key="base_currency", value="USD"),
    ])
    tpl = {"kind": "expense", "amount": 9.99, "currency": "USD", "account_id": 1, "category_id": 1,
           "merchant": "Spotify", "note": "monthly subscription"}
    session.add(RecurringRule(
        id=1, name="Spotify", rrule="FREQ=MONTHLY;BYMONTHDAY=1",
        template_json=json.dumps(tpl), next_run_at=dt.date(2026, 5, 1), active=1))
    await session.commit()
    return session


async def test_materialize_inserts_when_due(seeded):
    n = await materialize_due(seeded, today=dt.date(2026, 5, 1))
    assert n == 1
    rows = (await seeded.execute(select(Transaction))).scalars().all()
    assert len(rows) == 1
    assert rows[0].source == "recurring"
    assert rows[0].recurring_id == 1
    rule = (await seeded.execute(select(RecurringRule))).scalar_one()
    assert rule.next_run_at == dt.date(2026, 6, 1)
    assert rule.last_run_at == dt.date(2026, 5, 1)


async def test_materialize_skips_when_not_due(seeded):
    n = await materialize_due(seeded, today=dt.date(2026, 4, 30))
    assert n == 0
    assert (await seeded.execute(select(Transaction))).scalars().all() == []


async def test_materialize_skips_inactive(seeded):
    rule = (await seeded.execute(select(RecurringRule))).scalar_one()
    rule.active = 0
    await seeded.commit()
    n = await materialize_due(seeded, today=dt.date(2026, 5, 1))
    assert n == 0

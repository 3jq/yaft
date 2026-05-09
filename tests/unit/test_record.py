import datetime as dt

import pytest
from sqlalchemy import select

from finance_app.db.models import Account, Category, Currency, Setting, Transaction
from finance_app.pipeline.record import record
from finance_app.pipeline.resolver import ResolvedTransaction


@pytest.fixture
async def seeded(session):
    session.add_all([
        Currency(code="USD", name="USD"),
        Account(id=1, name="Cash", kind="cash", currency="USD"),
        Category(id=1, name="Food", kind="expense"),
        Setting(key="base_currency", value="USD"),
    ])
    await session.commit()
    return session


async def test_record_inserts_with_metadata(seeded):
    r = ResolvedTransaction(
        occurred_at=dt.datetime(2026, 5, 9, 12, 0),
        account_id=1,
        category_id=1,
        kind="expense",
        amount_minor=1250,
        currency="USD",
        base_amount_minor=1250,
        fx_rate=1.0,
        base_currency="USD",
        note="lunch",
        confidence=0.9,
        ambiguities=["x"],
    )
    tx = await record(seeded, r, source="text", source_ref="42", raw_input="12.50 lunch")
    assert tx.id is not None
    rows = (await seeded.execute(select(Transaction))).scalars().all()
    assert rows[0].source == "text"
    assert rows[0].raw_input == "12.50 lunch"
    assert rows[0].confidence == 0.9
    assert rows[0].group_id is not None  # always assigned

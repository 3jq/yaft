from datetime import datetime

import pytest
from sqlalchemy import select

from finance_app.db.models import Account, Category, Currency, Transaction
from finance_app.db.session import Base, make_engine, make_sessionmaker


@pytest.fixture
async def session():
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = make_sessionmaker(engine)
    async with Session() as s:
        yield s
    await engine.dispose()


async def test_create_account_and_transaction(session):
    session.add(Currency(code="USD", name="US Dollar"))
    acc = Account(name="Cash", kind="cash", currency="USD")
    cat = Category(name="Food", kind="expense")
    session.add_all([acc, cat])
    await session.flush()
    tx = Transaction(
        group_id="g1",
        account_id=acc.id,
        category_id=cat.id,
        kind="expense",
        amount_minor=1250,
        currency="USD",
        base_amount_minor=1250,
        fx_rate=1.0,
        merchant="Pret",
        source="text",
        raw_input="$12.50 lunch",
        confidence=1.0,
        occurred_at=datetime(2026, 5, 9, 12, 0, 0),
    )
    session.add(tx)
    await session.commit()
    rows = (await session.execute(select(Transaction))).scalars().all()
    assert len(rows) == 1
    assert rows[0].amount_minor == 1250

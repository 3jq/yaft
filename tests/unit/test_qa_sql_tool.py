import datetime as dt

import pytest

from yaft.analysis.qa_sql_tool import ReadOnlySQL
from yaft.db.models import Account, Currency, Transaction
from yaft.db.session import Base, make_engine, make_sessionmaker


@pytest.fixture
async def ro(tmp_path):
    """Seed data via a normal session, return a ReadOnlySQL backed by the same file."""
    db_file = tmp_path / "test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = make_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = make_sessionmaker(engine)
    async with Session() as s:
        s.add_all([
            Currency(code="USD", name="USD"),
            Account(id=1, name="Cash", kind="cash", currency="USD"),
            Transaction(
                group_id="g",
                occurred_at=dt.datetime(2026, 5, 9),
                account_id=1,
                kind="expense",
                amount_minor=1000,
                currency="USD",
                base_amount_minor=1000,
                fx_rate=1.0,
            ),
        ])
        await s.commit()
    await engine.dispose()
    ro_sql = ReadOnlySQL(db_url)
    yield ro_sql
    await ro_sql.aclose()


async def test_select_returns_rows(ro):
    rows = await ro.run_sql("SELECT amount_minor FROM transactions")
    assert rows == [{"amount_minor": 1000}]


async def test_rejects_write_statements(ro):
    with pytest.raises(ValueError):
        await ro.run_sql("DELETE FROM transactions")
    with pytest.raises(ValueError):
        await ro.run_sql("UPDATE transactions SET amount_minor=0")
    with pytest.raises(ValueError):
        await ro.run_sql("PRAGMA writable_schema=1")


async def test_caps_rows(ro):
    rows = await ro.run_sql(
        "SELECT 1 AS x UNION ALL SELECT 2 UNION ALL SELECT 3", limit=2
    )
    assert len(rows) == 2

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock

import pytest

from yaft.db.models import Account, Budget, Category, Currency, Setting, Transaction
from yaft.db.session import Base, make_engine, make_sessionmaker
from yaft.scheduler import jobs


@pytest.fixture
async def Session():
    """Real async_sessionmaker against in-memory SQLite, yielded for job use."""
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = make_sessionmaker(engine)
    yield sm
    await engine.dispose()


async def _seed(Session, rows: list) -> None:
    """Insert rows into the database via the sessionmaker."""
    async with Session() as s:
        s.add_all(rows)
        await s.commit()


async def test_check_budget_alerts_sends_message(Session):
    """check_budget_alerts should send a Telegram message when a budget is exceeded."""
    today = dt.datetime.now()

    await _seed(
        Session,
        [
            Currency(code="USD", name="US Dollar"),
            Account(id=1, name="Cash", kind="cash", currency="USD"),
            Category(id=1, name="Food", kind="expense"),
            Setting(key="base_currency", value="USD"),
            # Expense that exceeds the budget (1000 minor > budget 500 minor)
            Transaction(
                group_id="g1",
                occurred_at=today,
                account_id=1,
                category_id=1,
                kind="expense",
                amount_minor=1000,
                currency="USD",
                base_amount_minor=1000,
                fx_rate=1.0,
            ),
            Budget(
                id=1,
                category_id=1,
                amount_minor=500,
                currency="USD",
                alert_thresholds="[1.0]",
            ),
        ],
    )

    bot = MagicMock()
    bot.send_message = AsyncMock()

    n = await jobs.check_budget_alerts(Session, bot=bot, owner_id=12345)

    assert n == 1
    bot.send_message.assert_called_once()
    call_args = bot.send_message.call_args
    assert call_args[0][0] == 12345  # owner_id passed correctly
    assert "Food" in call_args[0][1]  # category name in message


async def test_check_budget_alerts_no_breach(Session):
    """check_budget_alerts should not send any message when no budget is exceeded."""
    today = dt.datetime.now()

    await _seed(
        Session,
        [
            Currency(code="USD", name="US Dollar"),
            Account(id=1, name="Cash", kind="cash", currency="USD"),
            Category(id=1, name="Food", kind="expense"),
            Setting(key="base_currency", value="USD"),
            # Expense below the budget
            Transaction(
                group_id="g2",
                occurred_at=today,
                account_id=1,
                category_id=1,
                kind="expense",
                amount_minor=100,
                currency="USD",
                base_amount_minor=100,
                fx_rate=1.0,
            ),
            Budget(
                id=1,
                category_id=1,
                amount_minor=500,
                currency="USD",
                alert_thresholds="[1.0]",
            ),
        ],
    )

    bot = MagicMock()
    bot.send_message = AsyncMock()

    n = await jobs.check_budget_alerts(Session, bot=bot, owner_id=12345)

    assert n == 0
    bot.send_message.assert_not_called()


async def test_materialize_recurring_no_rules(Session):
    """materialize_recurring should return 0 when no rules are due."""
    n = await jobs.materialize_recurring(Session)
    assert n == 0


async def test_fetch_fx_rates_no_accounts(Session):
    """fetch_fx_rates should return 0 when no accounts exist."""
    n = await jobs.fetch_fx_rates(Session)
    assert n == 0


async def test_weekly_digest_skeleton_sends_message(Session):
    """weekly_digest_skeleton should send a weekly digest message."""
    today = dt.datetime.now()

    await _seed(
        Session,
        [
            Currency(code="USD", name="US Dollar"),
            Account(id=1, name="Cash", kind="cash", currency="USD"),
            Category(id=1, name="Food", kind="expense"),
            Setting(key="base_currency", value="USD"),
            Transaction(
                group_id="g3",
                occurred_at=today,
                account_id=1,
                category_id=1,
                kind="expense",
                amount_minor=5000,
                currency="USD",
                base_amount_minor=5000,
                fx_rate=1.0,
            ),
            Transaction(
                group_id="g4",
                occurred_at=today,
                account_id=1,
                category_id=1,
                kind="income",
                amount_minor=10000,
                currency="USD",
                base_amount_minor=10000,
                fx_rate=1.0,
            ),
        ],
    )

    bot = MagicMock()
    bot.send_message = AsyncMock()

    await jobs.weekly_digest_skeleton(Session, bot=bot, owner_id=12345)

    bot.send_message.assert_called_once()
    msg = bot.send_message.call_args[0][1]
    assert "50.00 USD" in msg   # expense
    assert "100.00 USD" in msg  # income

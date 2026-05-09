import datetime as dt
from unittest.mock import AsyncMock, MagicMock

import pytest

from yaft.bot.handlers.commands import cmd_balance, cmd_help, cmd_list, cmd_start
from yaft.db.models import Account, Category, Currency, Setting, Transaction


@pytest.fixture
async def seeded(session):
    session.add_all([
        Currency(code="USD", name="USD"),
        Account(id=1, name="Cash", kind="cash", currency="USD", opening_balance_minor=10000),
        Category(id=1, name="Food", kind="expense"),
        Setting(key="base_currency", value="USD"),
        Transaction(id=1, group_id="g", occurred_at=dt.datetime(2026,5,9),
                    account_id=1, category_id=1, kind="expense",
                    amount_minor=1250, currency="USD",
                    base_amount_minor=1250, fx_rate=1.0),
    ])
    await session.commit()
    return session

async def test_start_replies(seeded):
    msg = MagicMock()
    msg.answer = AsyncMock()
    await cmd_start(msg)
    msg.answer.assert_called_once()

async def test_help_replies(seeded):
    msg = MagicMock()
    msg.answer = AsyncMock()
    await cmd_help(msg)
    assert "12.50" in msg.answer.call_args.args[0]

async def test_balance_includes_account(seeded):
    msg = MagicMock()
    msg.answer = AsyncMock()
    await cmd_balance(msg, seeded)
    text = msg.answer.call_args.args[0]
    assert "Cash" in text
    assert "USD" in text

async def test_list_shows_recent(seeded):
    msg = MagicMock()
    msg.answer = AsyncMock()
    await cmd_list(msg, seeded)
    text = msg.answer.call_args.args[0]
    assert "12.50" in text

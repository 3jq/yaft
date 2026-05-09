import datetime as dt
from unittest.mock import AsyncMock, MagicMock

import pytest

from finance_app.bot.handlers.callbacks import handle_callback
from finance_app.db.models import (
    Account,
    Category,
    Currency,
    Setting,
    Transaction,
)


@pytest.fixture
async def with_tx(session):
    session.add_all(
        [
            Currency(code="USD", name="USD"),
            Account(id=1, name="Cash", kind="cash", currency="USD"),
            Category(id=1, name="Food", kind="expense"),
            Setting(key="base_currency", value="USD"),
            Transaction(
                id=10,
                group_id="g1",
                occurred_at=dt.datetime(2026, 5, 9, 12, 0),
                account_id=1,
                category_id=1,
                kind="expense",
                amount_minor=1250,
                currency="USD",
                base_amount_minor=1250,
                fx_rate=1.0,
            ),
        ]
    )
    await session.commit()
    return session


async def test_callback_delete_soft_deletes(with_tx):
    cb = MagicMock()
    cb.data = "tx:del:10"
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    await handle_callback(cb, with_tx)
    tx = await with_tx.get(Transaction, 10)
    assert tx.deleted_at is not None
    cb.message.edit_text.assert_called_once()
    assert "deleted" in cb.message.edit_text.call_args.args[0].lower()


async def test_callback_unknown_action_acks_with_message(with_tx):
    cb = MagicMock()
    cb.data = "tx:edit:10"
    cb.answer = AsyncMock()
    await handle_callback(cb, with_tx)
    cb.answer.assert_called_once()

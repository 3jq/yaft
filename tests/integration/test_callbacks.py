import datetime as dt
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx
from sqlalchemy import select

from finance_app.bot.handlers.callbacks import handle_callback
from finance_app.bot.parser_text import ParsedTransaction
from finance_app.db.models import (
    Account,
    Category,
    Currency,
    Setting,
    Transaction,
)
from finance_app.pipeline.openrouter import OpenRouterClient


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


# Phase 2 additions


@pytest.fixture
async def with_voice_tx(session):
    session.add_all([
        Currency(code="USD", name="USD"),
        Account(id=1, name="Cash", kind="cash", currency="USD"),
        Category(id=1, name="Food", kind="expense"),
        Setting(key="base_currency", value="USD"),
        Setting(key="default_account_id", value="1"),
        Setting(key="timezone", value="UTC"),
        Transaction(
            id=10, group_id="g", occurred_at=dt.datetime(2026, 5, 9),
            account_id=1, category_id=1, kind="expense",
            amount_minor=999, currency="USD",
            base_amount_minor=999, fx_rate=1.0,
            source="voice", raw_input="originally said 25 dollars for lunch",
        ),
    ])
    await session.commit()
    return session


@respx.mock
async def test_callback_retry_reparses(with_voice_tx):
    respx.get("https://open.er-api.com/v6/latest/USD").mock(
        return_value=httpx.Response(200, json={
            "result": "success", "base_code": "USD", "rates": {"USD": 1.0},
        }))
    llm = MagicMock(spec=OpenRouterClient)
    llm.parse_transaction = AsyncMock(return_value=ParsedTransaction(
        kind="expense", amount=25, currency="USD", account="Cash",
        category="Food", occurred_at=dt.datetime(2026, 5, 9), confidence=0.95,
    ))
    cb = MagicMock()
    cb.data = "tx:retry:10"
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    await handle_callback(cb, with_voice_tx, llm=llm, http_client=httpx.AsyncClient())
    rows = (await with_voice_tx.execute(select(Transaction))).scalars().all()
    # Old soft-deleted, new row present
    assert any(t.deleted_at is not None and t.id == 10 for t in rows)
    assert any(t.deleted_at is None and t.amount_minor == 2500 for t in rows)
    llm.parse_transaction.assert_called_once()

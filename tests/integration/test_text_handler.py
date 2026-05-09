import datetime as dt
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx
from sqlalchemy import select

from finance_app.bot.handlers.text import handle_text
from finance_app.bot.parser_text import ParsedTransaction
from finance_app.db.models import Account, Category, Currency, Setting, Transaction
from finance_app.pipeline.openrouter import OpenRouterClient


@pytest.fixture
async def seeded(session):
    session.add_all([
        Currency(code="USD", name="USD"),
        Currency(code="AED", name="AED"),
        Account(id=1, name="Cash", kind="cash", currency="USD"),
        Account(id=2, name="Revolut AED", kind="bank", currency="AED"),
        Category(id=1, name="Food", kind="expense"),
        Category(id=2, name="Lunch", parent_id=1, kind="expense"),
        Setting(key="base_currency", value="USD"),
        Setting(key="default_account_id", value="1"),
    ])
    await session.commit()
    return session


@respx.mock
async def test_text_message_records_and_replies(seeded):
    respx.get("https://open.er-api.com/v6/latest/AED").mock(
        return_value=httpx.Response(200, json={
            "result": "success", "base_code": "AED", "rates": {"USD": 0.272},
        }))
    msg = MagicMock()
    msg.text = "12.50 AED lunch at Pret #lunch @revolut"
    msg.message_id = 99
    msg.from_user.id = 1
    msg.answer = AsyncMock()
    await handle_text(
        msg, seeded, http_client=httpx.AsyncClient(), now=dt.datetime(2026, 5, 9, 12, 0)
    )
    assert msg.answer.called
    rows = (await seeded.execute(select(Transaction))).scalars().all()
    assert len(rows) == 1
    assert rows[0].amount_minor == 1250
    assert rows[0].currency == "AED"


@respx.mock
async def test_text_message_unparseable_replies_error(seeded):
    msg = MagicMock()
    msg.text = "hello"
    msg.message_id = 1
    msg.from_user.id = 1
    msg.answer = AsyncMock()
    await handle_text(msg, seeded, http_client=httpx.AsyncClient(), now=dt.datetime(2026, 5, 9))
    msg.answer.assert_called_once()
    reply = msg.answer.call_args.args[0].lower()
    assert "couldn't" in reply or "parse" in reply


# Phase 2 additions


@respx.mock
async def test_freeform_text_uses_llm(seeded):
    respx.get("https://open.er-api.com/v6/latest/USD").mock(
        return_value=httpx.Response(200, json={
            "result": "success", "base_code": "USD", "rates": {"USD": 1.0},
        }))
    llm = MagicMock(spec=OpenRouterClient)
    llm.parse_transaction = AsyncMock(return_value=ParsedTransaction(
        kind="expense", amount=12.5, currency="USD", account="Cash",
        category="Food", occurred_at=dt.datetime(2026, 5, 9), confidence=0.9,
    ))
    msg = MagicMock()
    msg.text = "had lunch yesterday"
    msg.message_id = 1
    msg.from_user.id = 1
    msg.answer = AsyncMock()
    await handle_text(
        msg, seeded, http_client=httpx.AsyncClient(),
        now=dt.datetime(2026, 5, 9), llm=llm,
    )
    rows = (await seeded.execute(select(Transaction))).scalars().all()
    assert len(rows) == 1


async def test_regex_fastpath_skips_llm(seeded):
    llm = MagicMock()
    llm.parse_transaction = AsyncMock()
    msg = MagicMock()
    msg.text = "12.50 lunch"
    msg.message_id = 1
    msg.from_user.id = 1
    msg.answer = AsyncMock()
    with respx.mock:
        respx.get("https://open.er-api.com/v6/latest/USD").mock(
            return_value=httpx.Response(200, json={
                "result": "success", "base_code": "USD", "rates": {"USD": 1.0},
            }))
        await handle_text(
            msg, seeded, http_client=httpx.AsyncClient(),
            now=dt.datetime(2026, 5, 9), llm=llm,
        )
    llm.parse_transaction.assert_not_called()


async def test_transfer_text_skips_fastpath_uses_llm(seeded):
    llm = MagicMock(spec=OpenRouterClient)
    llm.parse_transaction = AsyncMock(return_value=ParsedTransaction(
        kind="transfer", amount=500, currency="USD", account="Cash",
        transfer_to_account="Revolut AED",
        occurred_at=dt.datetime(2026, 5, 9), confidence=0.9,
    ))
    msg = MagicMock()
    msg.text = "500 USD transfer to Revolut"
    msg.message_id = 1
    msg.from_user.id = 1
    msg.answer = AsyncMock()
    with respx.mock:
        respx.get("https://open.er-api.com/v6/latest/USD").mock(
            return_value=httpx.Response(200, json={
                "result": "success", "base_code": "USD", "rates": {"USD": 1.0},
            }))
        await handle_text(msg, seeded, http_client=httpx.AsyncClient(),
                          now=dt.datetime(2026, 5, 9), llm=llm)
    llm.parse_transaction.assert_called_once()

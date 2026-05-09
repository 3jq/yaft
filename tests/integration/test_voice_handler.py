import datetime as dt
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx
from sqlalchemy import select

from yaft.bot.handlers.voice import handle_voice
from yaft.bot.parser_text import ParsedTransaction
from yaft.db.models import Account, Category, Currency, Setting, Transaction
from yaft.pipeline.openrouter import OpenRouterClient


@pytest.fixture
async def seeded(session):
    session.add_all([
        Currency(code="USD", name="USD"),
        Currency(code="AED", name="AED"),
        Account(id=1, name="Cash", kind="cash", currency="USD"),
        Account(id=2, name="Revolut AED", kind="bank", currency="AED"),
        Category(id=1, name="Food", kind="expense"),
        Setting(key="base_currency", value="USD"),
        Setting(key="default_account_id", value="1"),
        Setting(key="timezone", value="UTC"),
    ])
    await session.commit()
    return session


@respx.mock
async def test_voice_full_pipeline(seeded):
    respx.get("https://open.er-api.com/v6/latest/AED").mock(
        return_value=httpx.Response(200, json={
            "result": "success", "base_code": "AED", "rates": {"USD": 0.272},
        }))

    bot = MagicMock()

    async def fake_download(file_id, destination):
        destination.write(b"\x00\x00")
    bot.download = AsyncMock(side_effect=fake_download)

    client = MagicMock(spec=OpenRouterClient)
    client.transcribe = AsyncMock(return_value="купил кофе за 25 дирхам")
    client.parse_transaction = AsyncMock(return_value=ParsedTransaction(
        kind="expense", amount=25, currency="AED",
        account="Revolut AED", category="Food/Coffee",
        occurred_at=dt.datetime(2026, 5, 9, 12, 0), confidence=0.95,
    ))

    msg = MagicMock()
    msg.voice.file_id = "FID"
    msg.voice.duration = 3
    msg.message_id = 7
    msg.from_user.id = 1
    msg.answer = AsyncMock()

    await handle_voice(msg, seeded, bot=bot, llm=client, http_client=httpx.AsyncClient())

    rows = (await seeded.execute(select(Transaction))).scalars().all()
    assert len(rows) == 1
    assert rows[0].source == "voice"
    assert rows[0].raw_input == "купил кофе за 25 дирхам"
    assert msg.answer.called


async def test_voice_stt_failure_replies(seeded):
    bot = MagicMock()
    bot.download = AsyncMock()
    client = MagicMock()
    client.transcribe = AsyncMock(side_effect=RuntimeError("stt down"))
    msg = MagicMock()
    msg.voice.file_id = "x"
    msg.voice.duration = 2
    msg.message_id = 1
    msg.from_user.id = 1
    msg.answer = AsyncMock()
    await handle_voice(msg, seeded, bot=bot, llm=client, http_client=httpx.AsyncClient())
    assert "transcribe" in msg.answer.call_args.args[0].lower()


async def test_voice_parse_failure_replies_with_transcript(seeded):
    bot = MagicMock()

    async def fake_download(fid, destination):
        destination.write(b"\x00")
    bot.download = AsyncMock(side_effect=fake_download)
    client = MagicMock()
    client.transcribe = AsyncMock(return_value="hello world")
    client.parse_transaction = AsyncMock(side_effect=ValueError("bad json"))
    msg = MagicMock()
    msg.voice.file_id = "x"
    msg.voice.duration = 2
    msg.message_id = 1
    msg.from_user.id = 1
    msg.answer = AsyncMock()
    await handle_voice(msg, seeded, bot=bot, llm=client, http_client=httpx.AsyncClient())
    text = msg.answer.call_args.args[0]
    assert "hello world" in text

import json
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

import pytest

from finance_app.bot.parser_text import ParsedTransaction
from finance_app.pipeline.openrouter import OpenRouterClient, ParseContext


def _ok_parse_payload():
    return {
        "kind": "expense", "occurred_at": "2026-05-09T12:00:00",
        "amount": 25, "currency": "AED",
        "account": "Cash", "category": "Food/Coffee",
        "merchant": None, "note": "coffee",
        "transfer_to_account": None, "splits": None,
        "confidence": 0.92, "ambiguities": [],
    }


@pytest.fixture
def fake_sdk():
    sdk = MagicMock()
    # Two mocks: one for STT chat call, one for parse chat call.
    # We default to a single mock that returns the parse payload; tests override per-test.
    sdk.chat.completions.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(content=json.dumps(_ok_parse_payload())))]
    ))
    return sdk


async def test_transcribe(fake_sdk):
    fake_sdk.chat.completions.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(content="купил кофе за 25 дирхам"))]
    ))
    c = OpenRouterClient(sdk=fake_sdk)
    text = await c.transcribe(BytesIO(b"\x00\x01"), language_hint="ru")
    assert "кофе" in text
    # verify the call sent input_audio content
    kwargs = fake_sdk.chat.completions.create.call_args.kwargs
    msg_content = kwargs["messages"][-1]["content"]
    assert any(part.get("type") == "input_audio" for part in msg_content)


async def test_parse_returns_dataclass(fake_sdk):
    c = OpenRouterClient(sdk=fake_sdk)
    ctx = ParseContext(now_iso="2026-05-09T12:00:00",
                       timezone="UTC", base_currency="USD",
                       accounts=["Cash","Revolut AED"],
                       top_categories=["Food","Transport"])
    p = await c.parse_transaction("bought coffee for 25 AED", ctx)
    assert isinstance(p, ParsedTransaction)
    assert p.kind == "expense"
    assert p.amount == 25
    assert p.currency == "AED"
    assert p.category == "Food/Coffee"
    assert 0 <= p.confidence <= 1


async def test_parse_invalid_json_raises(fake_sdk):
    fake_sdk.chat.completions.create = AsyncMock(
        return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="not json"))])
    )
    c = OpenRouterClient(sdk=fake_sdk)
    ctx = ParseContext("2026-05-09T12:00:00","UTC","USD",[],[])
    with pytest.raises(ValueError):
        await c.parse_transaction("blah", ctx)


async def test_parse_with_hint_previous_was_wrong_includes_note(fake_sdk):
    c = OpenRouterClient(sdk=fake_sdk)
    ctx = ParseContext("2026-05-09T12:00:00","UTC","USD",[],[])
    await c.parse_transaction("redo this", ctx, hint_previous_was_wrong=True)
    msgs = fake_sdk.chat.completions.create.call_args.kwargs["messages"]
    assert "previous parse was wrong" in msgs[-1]["content"].lower()

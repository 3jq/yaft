import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from yaft.pipeline.openrouter import OpenRouterClient


@pytest.fixture
def fake_sdk():
    # First response: a tool call. Second response: final answer.
    sdk = MagicMock()
    seq = [
        MagicMock(choices=[MagicMock(message=MagicMock(
            content=None,
            tool_calls=[MagicMock(id="t1", function=MagicMock(
                name="run_sql",
                arguments=json.dumps(
                    {"query": "SELECT SUM(base_amount_minor) AS total FROM transactions"}
                ),
            ))],
        ))]),
        MagicMock(choices=[MagicMock(message=MagicMock(
            content="You spent $52 in total.", tool_calls=None
        ))]),
    ]
    sdk.chat.completions.create = AsyncMock(side_effect=seq)
    return sdk


async def test_ask_with_sql(fake_sdk):
    sql_runner = AsyncMock(return_value=[{"total": 5200}])
    c = OpenRouterClient(sdk=fake_sdk)
    answer = await c.ask_with_sql(
        "How much did I spend?",
        schema_text="-- schema...",
        sql_runner=sql_runner,
    )
    assert "$52" in answer
    sql_runner.assert_called_once()
    # Asserted sequence: tool call → tool result → final answer
    assert fake_sdk.chat.completions.create.call_count == 2

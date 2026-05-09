from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.integration.test_api_transactions import client, init_data_header  # noqa: F401


async def test_ask_endpoint_invokes_llm(client, monkeypatch):
    from yaft.api.routes import ask as ask_routes

    fake_llm = MagicMock()
    fake_llm.ask_with_sql = AsyncMock(return_value="You spent $12.50.")
    monkeypatch.setattr(ask_routes, "_llm_singleton", lambda req: fake_llm)

    h = {"X-Telegram-Init-Data": init_data_header()}
    r = await client.post("/api/ask", headers=h, json={"question": "how much in May?"})
    assert r.status_code == 200
    assert "12.50" in r.json()["answer"]

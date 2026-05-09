import datetime as dt
import hashlib
import hmac
import json
import time

import pytest
from httpx import ASGITransport, AsyncClient

from finance_app.app import make_app
from finance_app.config import get_settings
from finance_app.db.models import Account, Category, Currency, Setting, Transaction
from finance_app.db.session import Base

BOT_TOKEN = "1:fake"
OWNER = 42


def init_data_header(user_id: int = OWNER) -> str:
    auth_date = int(time.time())
    user = json.dumps({"id": user_id})
    pairs = {"auth_date": str(auth_date), "user": user}
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return "&".join([f"{k}={v}" for k, v in pairs.items()] + [f"hash={h}"])


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("OWNER_TG_ID", str(OWNER))
    monkeypatch.setenv("DB_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    get_settings.cache_clear()
    app = make_app()
    async with app.state.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = app.state.session_maker
    async with Session() as s:
        s.add_all([
            Currency(code="USD", name="USD"),
            Account(id=1, name="Cash", kind="cash", currency="USD"),
            Category(id=1, name="Food", kind="expense"),
            Setting(key="base_currency", value="USD"),
            Setting(key="default_account_id", value="1"),
            Transaction(id=10, group_id="g1", occurred_at=dt.datetime(2026, 5, 9),
                        account_id=1, category_id=1, kind="expense",
                        amount_minor=1250, currency="USD",
                        base_amount_minor=1250, fx_rate=1.0),
        ])
        await s.commit()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        yield ac


async def test_unauthenticated_rejected(client):
    r = await client.get("/api/transactions")
    assert r.status_code == 401


async def test_list_returns_transactions(client):
    r = await client.get(
        "/api/transactions",
        headers={"X-Telegram-Init-Data": init_data_header()},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["id"] == 10


async def test_patch_updates_fields(client):
    r = await client.patch(
        "/api/transactions/10",
        headers={"X-Telegram-Init-Data": init_data_header()},
        json={"note": "edited", "amount_minor": 2000},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["note"] == "edited"
    assert body["amount_minor"] == 2000


async def test_delete_soft_deletes_then_restore(client):
    h = {"X-Telegram-Init-Data": init_data_header()}
    r = await client.delete("/api/transactions/10", headers=h)
    assert r.status_code == 204
    r = await client.get("/api/transactions", headers=h)
    assert all(x["id"] != 10 for x in r.json())
    r = await client.post("/api/transactions/10/restore", headers=h)
    assert r.status_code == 204
    r = await client.get("/api/transactions", headers=h)
    assert any(x["id"] == 10 for x in r.json())


async def test_split_creates_legs(client):
    h = {"X-Telegram-Init-Data": init_data_header()}
    r = await client.post(
        "/api/transactions/10/split",
        headers=h,
        json={
            "splits": [
                {"category_id": 1, "amount_minor": 1000, "note": "a"},
                {"category_id": 1, "amount_minor": 250, "note": "b"},
            ]
        },
    )
    assert r.status_code == 200
    legs = r.json()
    assert len(legs) == 2
    assert sum(x["amount_minor"] for x in legs) == 1250


async def test_non_owner_forbidden(client):
    r = await client.get(
        "/api/transactions",
        headers={"X-Telegram-Init-Data": init_data_header(user_id=999)},
    )
    assert r.status_code == 403

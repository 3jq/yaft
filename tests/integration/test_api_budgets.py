import pytest
from tests.integration.test_api_transactions import client, init_data_header  # noqa: F401


async def test_create_and_progress(client):
    h = {"X-Telegram-Init-Data": init_data_header()}
    r = await client.post(
        "/api/budgets",
        headers=h,
        json={
            "category_id": 1,
            "amount_minor": 50000,
            "currency": "USD",
            "alert_thresholds": [0.8, 1.0],
        },
    )
    assert r.status_code == 201
    bid = r.json()["id"]
    r = await client.get("/api/budgets/progress", headers=h)
    assert r.status_code == 200
    rows = r.json()
    assert any(p["budget_id"] == bid for p in rows)


async def test_list_budgets(client):
    h = {"X-Telegram-Init-Data": init_data_header()}
    # create one
    r = await client.post(
        "/api/budgets",
        headers=h,
        json={"category_id": 1, "amount_minor": 10000, "currency": "USD"},
    )
    assert r.status_code == 201
    r = await client.get("/api/budgets", headers=h)
    assert r.status_code == 200
    assert len(r.json()) >= 1


async def test_delete_budget(client):
    h = {"X-Telegram-Init-Data": init_data_header()}
    r = await client.post(
        "/api/budgets",
        headers=h,
        json={"category_id": 1, "amount_minor": 20000, "currency": "USD"},
    )
    bid = r.json()["id"]
    r = await client.delete(f"/api/budgets/{bid}", headers=h)
    assert r.status_code == 204
    r = await client.get("/api/budgets", headers=h)
    assert not any(b["id"] == bid for b in r.json())


async def test_unauthenticated_rejected(client):
    r = await client.get("/api/budgets")
    assert r.status_code == 401

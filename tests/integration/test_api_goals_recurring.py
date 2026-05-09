import json

import pytest
from tests.integration.test_api_transactions import client, init_data_header  # noqa: F401


async def test_goal_create_and_progress(client):
    h = {"X-Telegram-Init-Data": init_data_header()}
    r = await client.post(
        "/api/goals",
        headers=h,
        json={
            "name": "Emergency",
            "target_minor": 100000,
            "currency": "USD",
            "progress_mode": "account_linked",
            "account_id": 1,
        },
    )
    assert r.status_code == 201
    r = await client.get("/api/goals/progress", headers=h)
    assert r.status_code == 200
    assert any(g["name"] == "Emergency" for g in r.json())


async def test_goal_list_and_archive(client):
    h = {"X-Telegram-Init-Data": init_data_header()}
    r = await client.post(
        "/api/goals",
        headers=h,
        json={
            "name": "Vacation",
            "target_minor": 50000,
            "currency": "USD",
            "progress_mode": "contribution_tagged",
        },
    )
    assert r.status_code == 201
    gid = r.json()["id"]
    r = await client.get("/api/goals", headers=h)
    assert any(g["id"] == gid for g in r.json())
    r = await client.post(f"/api/goals/{gid}/archive", headers=h)
    assert r.status_code == 204
    r = await client.get("/api/goals", headers=h)
    assert not any(g["id"] == gid for g in r.json())


async def test_recurring_crud(client):
    h = {"X-Telegram-Init-Data": init_data_header()}
    body = {
        "name": "Spotify",
        "rrule": "FREQ=MONTHLY;BYMONTHDAY=1",
        "template_json": json.dumps(
            {
                "kind": "expense",
                "amount": 9.99,
                "currency": "USD",
                "account_id": 1,
                "category_id": 1,
            }
        ),
        "next_run_at": "2026-06-01",
    }
    r = await client.post("/api/recurring", headers=h, json=body)
    assert r.status_code == 201
    rid = r.json()["id"]
    r = await client.post(f"/api/recurring/{rid}/pause", headers=h)
    assert r.status_code == 204
    # resume
    r = await client.post(f"/api/recurring/{rid}/resume", headers=h)
    assert r.status_code == 204
    # list
    r = await client.get("/api/recurring", headers=h)
    assert any(rec["id"] == rid for rec in r.json())
    # delete
    r = await client.delete(f"/api/recurring/{rid}", headers=h)
    assert r.status_code == 204


async def test_unauthenticated_rejected(client):
    r = await client.get("/api/goals")
    assert r.status_code == 401
    r = await client.get("/api/recurring")
    assert r.status_code == 401

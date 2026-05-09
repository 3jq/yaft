from tests.integration.test_api_transactions import client, init_data_header  # noqa: F401


async def test_create_and_list_accounts(client):  # noqa: F811
    h = {"X-Telegram-Init-Data": init_data_header()}
    r = await client.post(
        "/api/accounts",
        headers=h,
        json={
            "name": "Revolut EUR",
            "kind": "bank",
            "currency": "EUR",
            "opening_balance_minor": 12345,
        },
    )
    assert r.status_code == 201
    r = await client.get("/api/accounts", headers=h)
    assert any(a["name"] == "Revolut EUR" for a in r.json())


async def test_archive_account(client):  # noqa: F811
    h = {"X-Telegram-Init-Data": init_data_header()}
    r = await client.post("/api/accounts/1/archive", headers=h)
    assert r.status_code == 204
    r = await client.get("/api/accounts", headers=h)
    assert all(a["id"] != 1 for a in r.json())
    r = await client.get("/api/accounts?include_archived=true", headers=h)
    assert any(a["id"] == 1 and a["archived"] == 1 for a in r.json())


async def test_create_category_with_parent(client):  # noqa: F811
    h = {"X-Telegram-Init-Data": init_data_header()}
    r = await client.post(
        "/api/categories",
        headers=h,
        json={"name": "Coffee", "parent_id": 1, "kind": "expense", "emoji": "☕"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["parent_id"] == 1

from tests.integration.test_api_transactions import client, init_data_header  # noqa: F401


async def test_get_and_patch_settings(client):  # noqa: F811
    h = {"X-Telegram-Init-Data": init_data_header()}
    r = await client.get("/api/settings", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["base_currency"] == "USD"
    r = await client.patch("/api/settings", headers=h, json={"base_currency": "EUR"})
    assert r.status_code == 200
    assert r.json()["base_currency"] == "EUR"

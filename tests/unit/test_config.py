import os
from finance_app.config import Settings

def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "abc")
    monkeypatch.setenv("OWNER_TG_ID", "12345")
    monkeypatch.setenv("BASE_CURRENCY", "EUR")
    monkeypatch.setenv("TIMEZONE", "Europe/Berlin")
    monkeypatch.setenv("DB_URL", "sqlite+aiosqlite:///./x.db")
    s = Settings()
    assert s.bot_token == "abc"
    assert s.owner_tg_id == 12345
    assert s.base_currency == "EUR"

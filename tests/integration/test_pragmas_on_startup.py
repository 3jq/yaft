import pytest
from sqlalchemy import text

from finance_app.app import make_app
from finance_app.config import get_settings


@pytest.fixture
def app(monkeypatch, tmp_path):
    db = tmp_path / "f.db"
    monkeypatch.setenv("BOT_TOKEN", "1:x")
    monkeypatch.setenv("OWNER_TG_ID", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("DB_URL", f"sqlite+aiosqlite:///{db}")
    get_settings.cache_clear()
    return make_app()


async def test_journal_mode_is_wal(app):
    async with app.state.engine.connect() as c:
        mode = (await c.execute(text("PRAGMA journal_mode"))).scalar()
        assert mode == "wal"


async def test_fail_fast_missing_bot_token(monkeypatch, tmp_path):
    db = tmp_path / "f.db"
    monkeypatch.setenv("BOT_TOKEN", "")
    monkeypatch.setenv("OWNER_TG_ID", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("DB_URL", f"sqlite+aiosqlite:///{db}")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        make_app()
    get_settings.cache_clear()

import datetime as dt

import httpx
import pytest
import respx

from finance_app.bot.parser_text import ParsedTransaction
from finance_app.db.models import Account, Category, Currency, Setting
from finance_app.domain.fx import FxService
from finance_app.pipeline.resolver import Resolver


@pytest.fixture
async def seeded(session):
    session.add_all([
        Currency(code="USD", name="US Dollar"),
        Currency(code="AED", name="UAE Dirham"),
        Account(id=1, name="Cash", kind="cash", currency="USD"),
        Account(id=2, name="Revolut AED", kind="bank", currency="AED"),
        Category(id=1, name="Food", kind="expense"),
        Category(id=2, name="Lunch", parent_id=1, kind="expense"),
        Setting(key="base_currency", value="USD"),
        Setting(key="default_account_id", value="1"),
    ])
    await session.commit()
    return session


@respx.mock
async def test_resolve_with_explicit_account_and_category(seeded):
    respx.get("https://api.exchangerate.host/2026-05-09").mock(
        return_value=httpx.Response(200, json={"base": "AED", "rates": {"USD": 0.272}}))
    fx = FxService(seeded, http_client=httpx.AsyncClient())
    r = Resolver(seeded, fx)
    p = ParsedTransaction(kind="expense", amount=12.50, currency="AED",
                          account="revolut", category="lunch",
                          occurred_at=dt.datetime(2026, 5, 9, 12, 0))
    out = await r.resolve(p)
    assert out.account_id == 2
    assert out.category_id == 2
    assert out.amount_minor == 1250
    assert out.currency == "AED"
    assert out.base_amount_minor == round(1250 * 0.272)
    assert out.fx_rate == 0.272


async def test_resolve_falls_back_to_default_account(seeded):
    fx = FxService(seeded)
    r = Resolver(seeded, fx)
    p = ParsedTransaction(kind="expense", amount=10.0, currency="USD",
                          account=None, category=None,
                          occurred_at=dt.datetime(2026, 5, 9))
    out = await r.resolve(p)
    assert out.account_id == 1
    assert "default account" in " ".join(out.ambiguities).lower()
    assert out.confidence < 1.0


async def test_resolve_creates_new_category_under_parent(seeded):
    fx = FxService(seeded)
    r = Resolver(seeded, fx)
    p = ParsedTransaction(kind="expense", amount=5.0, currency="USD",
                          account="cash", category="Food/Coffee",
                          occurred_at=dt.datetime(2026, 5, 9))
    out = await r.resolve(p)
    cat = await seeded.get(Category, out.category_id)
    assert cat.name == "Coffee"
    assert cat.parent_id == 1  # Food
    assert out.confidence < 1.0

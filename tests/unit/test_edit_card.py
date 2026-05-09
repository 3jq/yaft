import datetime as dt

from finance_app.bot.edit_card import build_keyboard, render_card
from finance_app.db.models import Transaction


def test_render_card_basic():
    tx = Transaction(
        id=10,
        group_id="g",
        occurred_at=dt.datetime(2026, 5, 9, 12, 0),
        account_id=1,
        category_id=1,
        kind="expense",
        amount_minor=1250,
        currency="AED",
        base_amount_minor=340,
        fx_rate=0.272,
        merchant="Pret",
        note="with Sasha",
        confidence=0.9,
    )
    text = render_card(
        tx,
        account_name="Revolut AED",
        category_path="Food / Lunch",
        base_currency="USD",
    )
    assert "−12.50 AED" in text
    assert "≈ −3.40 USD" in text
    assert "Food / Lunch" in text
    assert "Revolut AED" in text

def test_render_card_low_confidence_warning():
    tx = Transaction(
        id=11,
        group_id="g",
        occurred_at=dt.datetime(2026, 5, 9, 12, 0),
        account_id=1,
        category_id=None,
        kind="expense",
        amount_minor=500,
        currency="USD",
        base_amount_minor=500,
        fx_rate=1.0,
        confidence=0.4,
    )
    text = render_card(
        tx, account_name="Cash", category_path=None, base_currency="USD"
    )
    assert "⚠️" in text

def test_keyboard_has_four_buttons():
    kb = build_keyboard(tx_id=10)
    rows = kb.inline_keyboard
    flat = [b.callback_data for r in rows for b in r]
    assert any(cd.endswith(":edit:10") for cd in flat)
    assert any(cd.endswith(":del:10") for cd in flat)
    assert any(cd.endswith(":retry:10") for cd in flat)
    assert any(cd.endswith(":split:10") for cd in flat)


def test_keyboard_edit_uses_webapp_when_base_given():
    kb = build_keyboard(tx_id=10, webapp_base="https://x.test/app")
    rows = kb.inline_keyboard
    edit = rows[0][0]
    assert edit.web_app is not None
    assert "/transactions/10" in edit.web_app.url
    split = rows[1][1]
    assert split.web_app is not None
    assert "/transactions/10" in split.web_app.url
    # Delete and Retry stay as callback buttons
    delete = rows[0][1]
    retry = rows[1][0]
    assert delete.callback_data == "tx:del:10"
    assert retry.callback_data == "tx:retry:10"


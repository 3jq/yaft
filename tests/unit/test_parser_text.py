from freezegun import freeze_time

from finance_app.bot.parser_text import parse_text


@freeze_time("2026-05-09 12:00:00")
def test_basic_amount_description():
    p = parse_text("12.50 lunch at Pret")
    assert p.kind == "expense"
    assert p.amount == 12.50
    assert p.currency is None
    assert p.note == "lunch at Pret"

def test_currency_in_amount():
    p = parse_text("12.50 AED lunch at Pret #food @cash")
    assert p.amount == 12.50
    assert p.currency == "AED"
    assert p.category == "food"
    assert p.account == "cash"
    assert p.note == "lunch at Pret"

def test_income_with_plus_prefix():
    p = parse_text("+3000 USD salary #salary")
    assert p.kind == "income"
    assert p.amount == 3000.0
    assert p.currency == "USD"
    assert p.category == "salary"

def test_unparseable_raises():
    import pytest
    with pytest.raises(ValueError):
        parse_text("hello world")

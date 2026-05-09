from hypothesis import given
from hypothesis import strategies as st

from yaft.domain.money import (
    convert,
    exponent,
    format_amount,
    from_minor,
    to_minor,
)


def test_exponent_known_currencies():
    assert exponent("USD") == 2
    assert exponent("EUR") == 2
    assert exponent("AED") == 2
    assert exponent("RUB") == 2
    assert exponent("JPY") == 0  # zero-decimal
    assert exponent("KWD") == 3  # three-decimal

def test_to_minor_rounds_half_even():
    assert to_minor(12.5, "USD") == 1250
    assert to_minor(12.505, "USD") == 1250  # banker's rounding
    assert to_minor(12.515, "USD") == 1252
    assert to_minor(100, "JPY") == 100
    assert to_minor(1.234, "KWD") == 1234

def test_from_minor_roundtrips():
    assert from_minor(1250, "USD") == 12.50
    assert from_minor(100, "JPY") == 100.0
    assert from_minor(1234, "KWD") == 1.234

def test_format_amount():
    assert format_amount(1250, "USD") == "12.50 USD"
    assert format_amount(-1250, "USD") == "-12.50 USD"
    assert format_amount(100, "JPY") == "100 JPY"

def test_convert_uses_rate_and_target_exponent():
    # 100.00 EUR @ 1.10 → 110.00 USD
    assert convert(10000, "EUR", "USD", rate=1.10) == 11000
    # 100.00 EUR → 11000 JPY at rate 110.0  (target exponent 0)
    assert convert(10000, "EUR", "JPY", rate=110.0) == 11000

def test_convert_same_currency_identity():
    assert convert(1234, "USD", "USD", rate=1.0) == 1234

@given(amount=st.integers(min_value=-10**9, max_value=10**9))
def test_from_minor_to_minor_roundtrip_usd(amount):
    assert to_minor(from_minor(amount, "USD"), "USD") == amount

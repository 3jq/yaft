from decimal import ROUND_HALF_EVEN, Decimal

# Minimal table; extend as needed.
_EXPONENTS = {
    "USD": 2, "EUR": 2, "GBP": 2, "AED": 2, "RUB": 2, "CHF": 2, "CAD": 2,
    "AUD": 2, "CNY": 2, "INR": 2, "TRY": 2, "PLN": 2, "CZK": 2, "SEK": 2,
    "JPY": 0, "KRW": 0,
    "KWD": 3, "BHD": 3, "OMR": 3, "TND": 3,
}

def exponent(code: str) -> int:
    return _EXPONENTS.get(code.upper(), 2)

def to_minor(amount: float | int | Decimal | str, code: str) -> int:
    q = Decimal(10) ** -exponent(code)
    d = Decimal(str(amount)).quantize(q, rounding=ROUND_HALF_EVEN)
    return int(d * (Decimal(10) ** exponent(code)))

def from_minor(minor: int, code: str) -> float:
    return float(Decimal(minor) / (Decimal(10) ** exponent(code)))

def format_amount(minor: int, code: str) -> str:
    e = exponent(code)
    sign = "-" if minor < 0 else ""
    n = abs(minor)
    if e == 0:
        return f"{sign}{n} {code}"
    whole, frac = divmod(n, 10**e)
    return f"{sign}{whole}.{frac:0{e}d} {code}"

def convert(minor_src: int, src: str, dst: str, *, rate: float) -> int:
    """Convert `minor_src` (in src minor units) to dst minor units using rate src→dst."""
    if src.upper() == dst.upper():
        return minor_src
    src_e = exponent(src)
    dst_e = exponent(dst)
    # scale: minor_dst = minor_src * rate * 10^(dst_e - src_e)
    factor = Decimal(rate) * (Decimal(10) ** (dst_e - src_e))
    return int((Decimal(minor_src) * factor).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))

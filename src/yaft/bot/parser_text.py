from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

_AMOUNT_RE = re.compile(r"^\s*(?P<sign>[+-]?)(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<ccy>[A-Za-z]{3})?\b")
_TAG_CAT = re.compile(r"#(\S+)")
_TAG_ACC = re.compile(r"@(\S+)")

@dataclass
class ParsedTransaction:
    kind: str
    amount: float
    currency: str | None = None
    occurred_at: datetime | None = None
    account: str | None = None
    category: str | None = None
    merchant: str | None = None
    note: str | None = None
    transfer_to_account: str | None = None
    splits: list[dict] | None = None
    confidence: float = 1.0
    ambiguities: list[str] = field(default_factory=list)

def parse_text(text: str) -> ParsedTransaction:
    m = _AMOUNT_RE.match(text)
    if not m:
        raise ValueError(f"couldn't parse amount from: {text!r}")
    sign = m.group("sign") or ""
    amount = float(m.group("amount").replace(",", "."))
    currency = m.group("ccy").upper() if m.group("ccy") else None
    rest = text[m.end():].strip()

    cat = None
    if cm := _TAG_CAT.search(rest):
        cat = cm.group(1).lower()
        rest = (rest[:cm.start()] + rest[cm.end():]).strip()
    acc = None
    if am := _TAG_ACC.search(rest):
        acc = am.group(1).lower()
        rest = (rest[:am.start()] + rest[am.end():]).strip()

    kind = "income" if sign == "+" else "expense"
    note = rest or None
    return ParsedTransaction(
        kind=kind, amount=amount, currency=currency,
        account=acc, category=cat, note=note, occurred_at=datetime.now(),
    )

def parsed_transaction_json_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "kind","occurred_at","amount","currency","account","category",
            "merchant","note","transfer_to_account","splits","confidence","ambiguities",
        ],
        "properties": {
            "kind": {"type": "string", "enum": ["expense", "income", "transfer"]},
            "occurred_at": {"type": "string", "format": "date-time"},
            "amount": {"type": "number"},
            "currency": {"type": ["string", "null"], "minLength": 3, "maxLength": 3},
            "account": {"type": ["string", "null"]},
            "category": {"type": ["string", "null"]},
            "merchant": {"type": ["string", "null"]},
            "note": {"type": ["string", "null"]},
            "transfer_to_account": {"type": ["string", "null"]},
            "splits": {
                "type": ["array", "null"],
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["category", "amount", "note"],
                    "properties": {
                        "category": {"type": "string"},
                        "amount": {"type": "number"},
                        "note": {"type": ["string", "null"]},
                    },
                },
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "ambiguities": {"type": "array", "items": {"type": "string"}},
        },
    }

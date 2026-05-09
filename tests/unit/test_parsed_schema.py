import jsonschema
import pytest

from finance_app.bot.parser_text import parsed_transaction_json_schema


def _minimal():
    return {
        "kind": "expense", "occurred_at": "2026-05-09T12:00:00",
        "amount": 40.0, "currency": "USD", "account": "Cash",
        "category": "Misc", "merchant": None, "note": None,
        "transfer_to_account": None, "splits": None,
        "confidence": 1.0, "ambiguities": [],
    }

def test_schema_validates_minimal_expense():
    schema = parsed_transaction_json_schema()
    instance = {**_minimal(), "currency": "AED", "category": "Food/Lunch", "confidence": 0.9}
    jsonschema.validate(instance, schema)

def test_schema_rejects_invalid_kind():
    schema = parsed_transaction_json_schema()
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**_minimal(), "kind": "loan"}, schema)

def test_schema_validates_split():
    schema = parsed_transaction_json_schema()
    instance = {**_minimal(), "splits": [
        {"category": "Food/Groceries", "amount": 30.0, "note": "milk+bread"},
        {"category": "Health",         "amount": 10.0, "note": "vitamins"},
    ]}
    jsonschema.validate(instance, schema)

import hashlib
import hmac
import json
import time

import pytest

from yaft.api.auth import InitDataError, verify_init_data

BOT_TOKEN = "12345:fake"


def _build(user_id: int, *, age_seconds: int = 10) -> str:
    auth_date = int(time.time()) - age_seconds
    user = json.dumps({"id": user_id, "first_name": "T"})
    pairs = {"auth_date": str(auth_date), "query_id": "Q", "user": user}
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return "&".join([f"{k}={v}" for k, v in pairs.items()] + [f"hash={h}"])


def test_valid_init_data_returns_user_id():
    init = _build(42)
    info = verify_init_data(init, bot_token=BOT_TOKEN)
    assert info.user_id == 42


def test_tampered_hash_rejected():
    init = _build(42).rsplit("=", 1)[0] + "=deadbeef"
    with pytest.raises(InitDataError):
        verify_init_data(init, bot_token=BOT_TOKEN)


def test_old_auth_date_rejected():
    init = _build(42, age_seconds=86400 + 60)
    with pytest.raises(InitDataError):
        verify_init_data(init, bot_token=BOT_TOKEN, max_age_seconds=86400)

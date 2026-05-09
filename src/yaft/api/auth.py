from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException, Request

from yaft.config import get_settings


class InitDataError(ValueError):
    pass


@dataclass
class InitDataInfo:
    user_id: int
    auth_date: int


def verify_init_data(
    init_data: str, *, bot_token: str, max_age_seconds: int = 86400
) -> InitDataInfo:
    pairs = dict(parse_qsl(init_data, strict_parsing=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InitDataError("missing hash")
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise InitDataError("bad hash")
    auth_date = int(pairs.get("auth_date", "0"))
    if max_age_seconds and abs(time.time() - auth_date) > max_age_seconds:
        raise InitDataError("auth_date too old")
    user = json.loads(pairs.get("user", "{}"))
    uid = int(user.get("id", 0))
    if not uid:
        raise InitDataError("missing user")
    return InitDataInfo(user_id=uid, auth_date=auth_date)


async def require_owner(
    request: Request,
    x_telegram_init_data: str = Header(default=""),
) -> InitDataInfo:
    settings = get_settings()
    try:
        info = verify_init_data(x_telegram_init_data, bot_token=settings.bot_token)
    except InitDataError as e:
        raise HTTPException(status_code=401, detail=f"auth failed: {e}") from e
    if info.user_id != settings.owner_tg_id:
        raise HTTPException(status_code=403, detail="not owner")
    return info

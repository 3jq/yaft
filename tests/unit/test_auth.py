from unittest.mock import MagicMock

from finance_app.bot.auth import OwnerOnly


class FakeUser:
    def __init__(self, id): self.id = id

def make_event(user_id):
    e = MagicMock()
    e.from_user = FakeUser(user_id)
    return e

async def test_owner_passes():
    f = OwnerOnly(owner_id=12345)
    assert await f(make_event(12345)) is True

async def test_non_owner_blocked():
    f = OwnerOnly(owner_id=12345)
    assert await f(make_event(99)) is False

async def test_no_user_blocked():
    f = OwnerOnly(owner_id=12345)
    e = MagicMock()
    e.from_user = None
    assert await f(e) is False

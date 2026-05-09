from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject


class OwnerOnly(BaseFilter):
    def __init__(self, owner_id: int):
        self.owner_id = owner_id

    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and user.id == self.owner_id)

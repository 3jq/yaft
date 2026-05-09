from __future__ import annotations

import datetime as dt

from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.db.models import Transaction


async def handle_callback(cb: CallbackQuery, session: AsyncSession) -> None:
    parts = (cb.data or "").split(":")
    if len(parts) != 3 or parts[0] != "tx":
        await cb.answer("Unknown action")
        return
    _, action, raw_id = parts
    try:
        tx_id = int(raw_id)
    except ValueError:
        await cb.answer("Bad id")
        return

    if action == "del":
        tx = await session.get(Transaction, tx_id)
        if tx and tx.deleted_at is None:
            tx.deleted_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)
            await session.commit()
        await cb.message.edit_text("🗑 Deleted (soft).")
        await cb.answer("Deleted")
        return
    if action in ("edit", "split"):
        await cb.answer("Coming in Phase 3 (WebApp)", show_alert=True)
        return
    if action == "retry":
        await cb.answer("Coming in Phase 2 (LLM)", show_alert=True)
        return
    await cb.answer("Unknown action")

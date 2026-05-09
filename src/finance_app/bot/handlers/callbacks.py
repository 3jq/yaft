from __future__ import annotations

import datetime as dt

import httpx
from aiogram.types import CallbackQuery
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.bot.edit_card import build_keyboard, render_card
from finance_app.bot.handlers.voice import _build_context
from finance_app.db.models import Account, Category, Transaction
from finance_app.domain.fx import FxService
from finance_app.pipeline.openrouter import OpenRouterClient
from finance_app.pipeline.record import record
from finance_app.pipeline.resolver import Resolver


async def handle_callback(
    cb: CallbackQuery,
    session: AsyncSession,
    *,
    llm: OpenRouterClient | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> None:
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
            now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
            if tx.group_id:
                await session.execute(
                    update(Transaction)
                    .where(Transaction.group_id == tx.group_id, Transaction.deleted_at.is_(None))
                    .values(deleted_at=now, updated_at=now)
                )
            else:
                tx.deleted_at = now
                tx.updated_at = now
            await session.commit()
        await cb.message.edit_text("🗑 Deleted (soft).")
        await cb.answer("Deleted")
        return

    if action == "retry":
        if llm is None or http_client is None:
            await cb.answer("Retry unavailable here", show_alert=True)
            return
        old = await session.get(Transaction, tx_id)
        if not old or not old.raw_input:
            await cb.answer("Nothing to retry", show_alert=True)
            return
        ctx = await _build_context(session)
        try:
            parsed = await llm.parse_transaction(old.raw_input, ctx, hint_previous_was_wrong=True)
        except Exception:
            await cb.answer("Re-parse failed", show_alert=True)
            return
        # Soft-delete the old transaction and any siblings that share its group_id
        # (transfer pairs, split legs).
        now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
        if old.group_id:
            await session.execute(
                update(Transaction)
                .where(Transaction.group_id == old.group_id, Transaction.deleted_at.is_(None))
                .values(deleted_at=now, updated_at=now)
            )
        else:
            old.deleted_at = now
            old.updated_at = now
        await session.commit()
        # Record new
        fx = FxService(session, http_client=http_client)
        try:
            resolved = await Resolver(session, fx).resolve(parsed)
        except (ValueError, RuntimeError) as e:
            await cb.message.answer(f"Re-parse OK but couldn't resolve: {e}")
            await cb.answer("Resolve failed", show_alert=True)
            return
        tx = await record(
            session, resolved, source=old.source or "voice",
            source_ref=old.source_ref, raw_input=old.raw_input,
        )
        acc = await session.get(Account, tx.account_id)
        cat_path = None
        if tx.category_id:
            c = await session.get(Category, tx.category_id)
            if c.parent_id:
                p = await session.get(Category, c.parent_id)
                cat_path = f"{p.name} / {c.name}"
            else:
                cat_path = c.name
        body = render_card(
            tx, account_name=acc.name, category_path=cat_path,
            base_currency=resolved.base_currency,
        )
        body = "🔁 Re-parsed.\n\n" + body
        await cb.message.answer(body, reply_markup=build_keyboard(tx.id))
        await cb.answer("Re-parsed")
        return

    if action in ("edit", "split"):
        await cb.answer("Coming in Phase 3 (WebApp)", show_alert=True)
        return

    await cb.answer("Unknown action")

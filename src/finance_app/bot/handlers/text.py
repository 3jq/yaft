from __future__ import annotations

import datetime as dt

import httpx
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.bot.edit_card import build_keyboard, render_card
from finance_app.bot.parser_text import parse_text
from finance_app.db.models import Account, Category
from finance_app.domain.fx import FxService
from finance_app.pipeline.record import record
from finance_app.pipeline.resolver import Resolver


async def handle_text(
    msg: Message,
    session: AsyncSession,
    *,
    http_client: httpx.AsyncClient,
    now: dt.datetime | None = None,
) -> None:
    text = (msg.text or "").strip()
    try:
        parsed = parse_text(text)
        if now is not None:
            parsed.occurred_at = now
    except ValueError:
        await msg.answer("Couldn't parse that. Try: `12.50 AED lunch #food @cash`")
        return

    fx = FxService(session, http_client=http_client)
    resolver = Resolver(session, fx)
    try:
        resolved = await resolver.resolve(parsed)
    except (ValueError, RuntimeError) as e:
        await msg.answer(f"Couldn't resolve that transaction: {e}")
        return
    tx = await record(session, resolved, source="text",
                      source_ref=str(msg.message_id), raw_input=text)

    acc = await session.get(Account, tx.account_id)
    cat_path = None
    if tx.category_id:
        c = await session.get(Category, tx.category_id)
        if c.parent_id:
            p = await session.get(Category, c.parent_id)
            cat_path = f"{p.name} / {c.name}"
        else:
            cat_path = c.name

    body = render_card(tx, account_name=acc.name, category_path=cat_path,
                       base_currency=resolved.base_currency)
    if resolved.ambiguities:
        body += "\n" + "; ".join(resolved.ambiguities)
    await msg.answer(body, reply_markup=build_keyboard(tx.id))

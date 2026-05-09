from __future__ import annotations

import datetime as dt
import re

import httpx
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.bot.edit_card import build_keyboard, render_card
from finance_app.bot.handlers.voice import _build_context
from finance_app.bot.parser_text import parse_text
from finance_app.db.models import Account, Category
from finance_app.domain.fx import FxService
from finance_app.pipeline.openrouter import OpenRouterClient
from finance_app.pipeline.record import record
from finance_app.pipeline.resolver import Resolver

_FASTPATH = re.compile(r"^\s*[+-]?\d+(?:[.,]\d+)?\s*[A-Za-z]{0,3}\b")
_AMBIGUOUS_KW = re.compile(r"\b(transfer|перевел|перевёл|split)\b", re.IGNORECASE)

_PARSE_ERR = "Couldn't parse that into a transaction. Try the WebApp to add manually."


async def handle_text(
    msg: Message,
    session: AsyncSession,
    *,
    http_client: httpx.AsyncClient,
    llm: OpenRouterClient | None = None,
    now: dt.datetime | None = None,
) -> None:
    text = (msg.text or "").strip()

    parsed = None
    if _FASTPATH.match(text) and not _AMBIGUOUS_KW.search(text):
        try:
            parsed = parse_text(text)
        except ValueError:
            parsed = None

    if parsed is None:
        if llm is None:
            await msg.answer("Couldn't parse that. Try: `12.50 AED lunch #food @cash`")
            return
        ctx = await _build_context(session)
        try:
            parsed = await llm.parse_transaction(text, ctx)
        except Exception:
            await msg.answer(_PARSE_ERR)
            return

    if now is not None:
        parsed.occurred_at = now

    fx = FxService(session, http_client=http_client)
    resolver = Resolver(session, fx)
    try:
        resolved = await resolver.resolve(parsed)
    except (ValueError, RuntimeError) as e:
        await msg.answer(f"Couldn't resolve that transaction: {e}")
        return
    tx = await record(
        session, resolved, source="text",
        source_ref=str(msg.message_id), raw_input=text,
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
    if resolved.ambiguities:
        body += "\n" + "; ".join(resolved.ambiguities)
    await msg.answer(body, reply_markup=build_keyboard(tx.id))

from __future__ import annotations

import datetime as dt
import re

import httpx
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from yaft.bot.edit_card import build_keyboard
from yaft.bot.handlers.voice import _build_context, _render_for
from yaft.bot.parser_text import parse_text
from yaft.config import get_settings
from yaft.domain.fx import FxService
from yaft.pipeline.openrouter import OpenRouterClient
from yaft.pipeline.record import record
from yaft.pipeline.resolver import Resolver

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

    body = await _render_for(session, tx, base_currency=resolved.base_currency)
    if resolved.ambiguities:
        body += "\n" + "; ".join(resolved.ambiguities)
    _settings = get_settings()
    webapp_base = (_settings.public_https_url + "/app") if _settings.public_https_url else None
    await msg.answer(body, reply_markup=build_keyboard(tx.id, webapp_base=webapp_base))

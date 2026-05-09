from __future__ import annotations

import datetime as dt
from io import BytesIO
from zoneinfo import ZoneInfo

import httpx
from aiogram import Bot
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.bot.edit_card import build_keyboard, render_card
from finance_app.db.models import Account, Category, Setting
from finance_app.domain.fx import FxService
from finance_app.pipeline.openrouter import OpenRouterClient, ParseContext
from finance_app.pipeline.record import record
from finance_app.pipeline.resolver import Resolver


async def _build_context(session: AsyncSession) -> ParseContext:
    base = (
        await session.execute(select(Setting).where(Setting.key == "base_currency"))
    ).scalar_one().value
    tz_row = (
        await session.execute(select(Setting).where(Setting.key == "timezone"))
    ).scalar_one_or_none()
    tz = tz_row.value if tz_row else "UTC"
    accs = [a.name for a in (await session.execute(
        select(Account).where(Account.archived == 0)
    )).scalars().all()]
    cats = [c.name for c in (await session.execute(
        select(Category).where(Category.parent_id.is_(None), Category.archived == 0)
    )).scalars().all()]
    try:
        now_local = dt.datetime.now(ZoneInfo(tz))
    except Exception:
        now_local = dt.datetime.now(dt.UTC)
    return ParseContext(
        now_iso=now_local.isoformat(), timezone=tz,
        base_currency=base, accounts=accs, top_categories=cats,
    )


async def handle_voice(
    msg: Message,
    session: AsyncSession,
    *,
    bot: Bot,
    llm: OpenRouterClient,
    http_client: httpx.AsyncClient,
) -> None:
    buf = BytesIO()
    try:
        await bot.download(msg.voice.file_id, destination=buf)
        buf.seek(0)
    except Exception as e:
        await msg.answer(f"Couldn't download audio ({e}).")
        return

    try:
        transcript = await llm.transcribe(buf)
    except Exception as e:
        await msg.answer(f"Couldn't transcribe: {e}")
        return

    ctx = await _build_context(session)
    try:
        parsed = await llm.parse_transaction(transcript, ctx)
    except Exception:
        await msg.answer(
            f'Heard: "{transcript}"\nBut couldn\'t parse to a transaction. '
            "Open the WebApp to enter manually."
        )
        return

    fx = FxService(session, http_client=http_client)
    resolver = Resolver(session, fx)
    try:
        resolved = await resolver.resolve(parsed)
    except (ValueError, RuntimeError) as e:
        await msg.answer(f'Heard: "{transcript}"\nCouldn\'t resolve: {e}')
        return
    tx = await record(
        session, resolved, source="voice",
        source_ref=str(msg.message_id), raw_input=transcript,
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
    body = f'📝 "{transcript}"\n\n' + body
    await msg.answer(body, reply_markup=build_keyboard(tx.id))

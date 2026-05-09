from __future__ import annotations

import datetime as dt
from io import BytesIO
from zoneinfo import ZoneInfo

import httpx
from aiogram import Bot
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yaft.bot.edit_card import build_keyboard, render_group_card
from yaft.config import get_settings
from yaft.db.models import Account, Category, Setting, Transaction
from yaft.domain.fx import FxService
from yaft.pipeline.openrouter import OpenRouterClient, ParseContext
from yaft.pipeline.record import record
from yaft.pipeline.resolver import Resolver


async def _render_for(session: AsyncSession, tx: Transaction, *, base_currency: str) -> str:
    """Fetch all live legs sharing tx.group_id and render as one card."""
    if tx.group_id:
        legs = (await session.execute(
            select(Transaction).where(
                Transaction.group_id == tx.group_id,
                Transaction.deleted_at.is_(None),
            ).order_by(Transaction.id)
        )).scalars().all()
    else:
        legs = [tx]
    accounts = (await session.execute(select(Account))).scalars().all()
    cats = (await session.execute(select(Category))).scalars().all()
    return render_group_card(
        list(legs),
        account_by_id={a.id: a for a in accounts},
        category_by_id={c.id: c for c in cats},
        base_currency=base_currency,
    )


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

    body = await _render_for(session, tx, base_currency=resolved.base_currency)
    if resolved.ambiguities:
        body += "\n" + "; ".join(resolved.ambiguities)
    body = f'📝 "{transcript}"\n\n' + body
    _settings = get_settings()
    webapp_base = (_settings.public_https_url + "/app") if _settings.public_https_url else None
    await msg.answer(body, reply_markup=build_keyboard(tx.id, webapp_base=webapp_base))

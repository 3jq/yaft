from __future__ import annotations

from aiogram.types import Message
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from yaft.db.models import Account, Transaction
from yaft.domain.money import format_amount


async def cmd_start(msg: Message) -> None:
    await msg.answer(
        "Hi! I record your transactions.\n"
        "Try: `12.50 AED lunch at Pret #food @cash`\n"
        "Use /help for command list.",
        parse_mode="Markdown",
    )

async def cmd_help(msg: Message) -> None:
    await msg.answer(
        "*Format*: `<amount> [CCY] description [#category] [@account]`\n"
        "*Income*: prefix with `+`\n"
        "Examples:\n"
        "  `12.50 AED lunch #food @cash`\n"
        "  `+3000 USD salary #salary`\n"
        "Commands: /balance /list /help",
        parse_mode="Markdown",
    )

async def _account_balance_minor(session: AsyncSession, account_id: int) -> tuple[int, str]:
    acc = await session.get(Account, account_id)
    rows = (await session.execute(
        select(Transaction).where(Transaction.account_id == account_id,
                                  Transaction.deleted_at.is_(None))
    )).scalars().all()
    bal = acc.opening_balance_minor
    for t in rows:
        if t.kind in ("expense", "transfer_out"):
            bal -= t.amount_minor
        elif t.kind in ("income", "transfer_in"):
            bal += t.amount_minor
    return bal, acc.currency

async def cmd_balance(msg: Message, session: AsyncSession) -> None:
    accs = (await session.execute(select(Account).where(Account.archived == 0))).scalars().all()
    lines = []
    for a in accs:
        bal, ccy = await _account_balance_minor(session, a.id)
        lines.append(f"• {a.name}: {format_amount(bal, ccy)}")
    await msg.answer("\n".join(lines) if lines else "No accounts.")

async def cmd_forecast(msg: Message, session: AsyncSession, *, llm) -> None:
    import datetime as dt
    from yaft.analysis.forecast import forecast
    f = await forecast(session, today=dt.date.today())
    prompt = (
        "Narrate this finance forecast in 3 short sentences (no markdown):\n"
        f"avg_daily_minor: {f['avg_daily_minor']}\n"
        f"eom_net_minor: {f['eom_net_minor']}\n"
        f"runway_months: {f['runway_months']}\n"
        f"days_to_goal: {f['days_to_goal']}\n"
        f"month: {f['month_label']}\n"
        "Money is in integer cents. Convert to dollars in your reply."
    )
    resp = await llm._sdk.chat.completions.create(
        model=llm._parse_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    await msg.answer(resp.choices[0].message.content or "(no narrative)")


async def cmd_ask(msg: Message, session: AsyncSession, *, llm, db_url: str) -> None:
    text = (msg.text or "").removeprefix("/ask").strip()
    if not text:
        await msg.answer("Usage: /ask how much did I spend on food this month?")
        return
    import datetime as dt
    from yaft.analysis.qa_sql_tool import ReadOnlySQL, schema_text
    from yaft.db.models import Setting
    settings_rows = (await session.execute(select(Setting))).scalars().all()
    settings_map = {r.key: r.value for r in settings_rows}
    context_text = (
        f"base_currency: {settings_map.get('base_currency', 'USD')}\n"
        f"timezone: {settings_map.get('timezone', 'UTC')}\n"
        f"today: {dt.date.today().isoformat()}\n"
    )
    ro = ReadOnlySQL(db_url)
    try:
        answer = await llm.ask_with_sql(
            text,
            schema_text=schema_text(),
            sql_runner=ro.run_sql,
            context_text=context_text,
        )
    finally:
        await ro.aclose()
    await msg.answer(answer or "(no answer)")


async def cmd_list(msg: Message, session: AsyncSession) -> None:
    rows = (await session.execute(
        select(Transaction).where(Transaction.deleted_at.is_(None))
        .order_by(desc(Transaction.occurred_at)).limit(10)
    )).scalars().all()
    if not rows:
        await msg.answer("No transactions yet.")
        return
    lines = []
    for t in rows:
        sign = "−" if t.kind in ("expense", "transfer_out") else "+"
        amount = format_amount(t.amount_minor, t.currency)
        note_part = f" — {t.note}" if t.note else ""
        lines.append(f"#{t.id} {t.occurred_at:%m-%d} {sign}{amount}{note_part}")
    await msg.answer("\n".join(lines))

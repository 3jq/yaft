from __future__ import annotations

import datetime as dt

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from yaft.db.models import Account, Category, Setting, Transaction
from yaft.domain.budgets import due_alerts, mark_fired, month_window
from yaft.domain.fx import FxService
from yaft.domain.money import format_amount
from yaft.domain.rrule import materialize_due
from yaft.logging_setup import log


async def backup(
    Session: async_sessionmaker,
    *,
    db_path: str,
    out_dir: str,
    rclone_remote: str | None,
) -> str:
    """Wrapper that runs the SQLite online backup. Session unused (kept for
    scheduler-symmetry with the other jobs)."""
    from yaft.scheduler.backup import backup_sqlite
    return await backup_sqlite(
        db_path=db_path, out_dir=out_dir, rclone_remote=rclone_remote
    )


async def heartbeat(
    Session: async_sessionmaker,
    *,
    bot: Bot,
    owner_id: int,
    backup_dir: str,
) -> None:
    """Daily DM verifying the service is alive: tx count, account count,
    most recent backup filename. Missing the DM = something's broken."""
    import os
    async with Session() as s:
        n_tx = (
            await s.execute(
                select(Transaction).where(Transaction.deleted_at.is_(None))
            )
        ).scalars().all()
        n_acc = (
            await s.execute(select(Account).where(Account.archived == 0))
        ).scalars().all()
    last_backup = "—"
    try:
        files = sorted(
            f for f in os.listdir(backup_dir) if f.endswith(".sqlite.gz")
        )
        if files:
            last_backup = files[-1]
    except OSError:
        pass
    try:
        await bot.send_message(
            owner_id,
            f"❤️ Alive · {len(n_tx)} tx · {len(n_acc)} accounts "
            f"· last backup: {last_backup}",
        )
    except Exception as exc:
        log.warning("scheduler.heartbeat.send_failed", error=str(exc))
    log.info(
        "scheduler.heartbeat", tx=len(n_tx), accounts=len(n_acc),
        last_backup=last_backup,
    )


async def materialize_recurring(Session: async_sessionmaker) -> int:
    """Materialize any recurring transactions that are due today."""
    async with Session() as s:
        n = await materialize_due(s, today=dt.date.today())
    log.info("scheduler.materialize_recurring", count=n)
    return n


async def check_budget_alerts(Session: async_sessionmaker, *, bot: Bot, owner_id: int) -> int:
    """Check for budget threshold breaches and send Telegram alerts."""
    n = 0
    async with Session() as s:
        alerts = await due_alerts(s, dt.date.today())
        for a in alerts:
            cat = await s.get(Category, a.category_id)
            cat_name = cat.name if cat else f"category#{a.category_id}"
            try:
                await bot.send_message(
                    owner_id,
                    f"⚠️ Budget alert · {cat_name}\n"
                    f"Spent {format_amount(a.spent_minor, 'USD')} of "
                    f"{format_amount(a.budget_minor, 'USD')} ({a.threshold * 100:.0f}% threshold)",
                )
                await mark_fired(s, a.budget_id, dt.date.today(), a.threshold)
                n += 1
            except Exception as exc:
                log.warning("scheduler.budget_alert.send_failed", error=str(exc))
        await s.commit()
    log.info("scheduler.check_budget_alerts", sent=n)
    return n


async def fetch_fx_rates(Session: async_sessionmaker) -> int:
    """Fetch FX rates for all currencies currently in use."""
    today = dt.date.today()
    n = 0
    async with Session() as s:
        rows = (await s.execute(select(Account.currency).distinct())).scalars().all()
        if not rows:
            return 0
        # Determine base currency from settings, default to USD
        setting_row = (
            await s.execute(select(Setting).where(Setting.key == "base_currency"))
        ).scalar_one_or_none()
        base = setting_row.value if setting_row else "USD"
        fx = FxService(s)
        for ccy in rows:
            if ccy.upper() == base.upper():
                continue
            try:
                await fx.get_rate(today, base, ccy)
                n += 1
            except Exception as exc:
                log.warning("scheduler.fetch_fx_rates.failed", currency=ccy, error=str(exc))
    log.info("scheduler.fetch_fx_rates", fetched=n)
    return n


async def monthly_summary(
    Session: async_sessionmaker, *, bot: Bot, owner_id: int, llm
) -> None:
    """Send a 5-bullet monthly summary narrative via LLM."""
    import datetime as dt

    from yaft.analysis.monthly import aggregate_monthly, write_summary_narrative

    async with Session() as s:
        agg = await aggregate_monthly(s, today=dt.date.today())
    narrative = await write_summary_narrative(llm, agg)
    try:
        await bot.send_message(
            owner_id,
            f"\U0001f4c5 Monthly summary {agg['month_label']}\n\n{narrative}",
        )
    except Exception as exc:
        log.warning("scheduler.monthly_summary.send_failed", error=str(exc))
    log.info("scheduler.monthly_summary", month=agg["month_label"])


async def weekly_coach(
    Session: async_sessionmaker, *, bot: Bot, owner_id: int, llm
) -> None:
    """Send a weekly savings-coach narrative powered by LLM."""
    import datetime as dt

    from yaft.analysis.weekly import coach_narrative, gather

    async with Session() as s:
        snap = await gather(s, today=dt.date.today())
    text = await coach_narrative(llm, snap)
    try:
        await bot.send_message(owner_id, f"\U0001f4ca Weekly check-in\n\n{text}")
    except Exception as exc:
        log.warning("scheduler.weekly_coach.send_failed", error=str(exc))
    log.info("scheduler.weekly_coach")


async def weekly_digest_skeleton(Session: async_sessionmaker, *, bot: Bot, owner_id: int) -> None:
    """Send a basic month-to-date digest. Phase 5 will replace with LLM narrative."""
    today = dt.date.today()
    async with Session() as s:
        start, end = month_window(today)
        rows = (
            await s.execute(
                select(Transaction).where(
                    Transaction.deleted_at.is_(None),
                    Transaction.occurred_at >= start,
                    Transaction.occurred_at < end,
                )
            )
        ).scalars().all()
        spent = sum(t.base_amount_minor for t in rows if t.kind == "expense")
        income = sum(t.base_amount_minor for t in rows if t.kind == "income")

        # Determine display currency from settings
        setting_row = (
            await s.execute(select(Setting).where(Setting.key == "base_currency"))
        ).scalar_one_or_none()
        ccy = setting_row.value if setting_row else "USD"

    try:
        await bot.send_message(
            owner_id,
            f"\U0001f4ca Weekly digest\n"
            f"Month-to-date income: {format_amount(income, ccy)}\n"
            f"Month-to-date expense: {format_amount(spent, ccy)}",
        )
    except Exception as exc:
        log.warning("scheduler.weekly_digest.send_failed", error=str(exc))
    log.info("scheduler.weekly_digest_skeleton", income=income, spent=spent)

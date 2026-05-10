from __future__ import annotations

import asyncio
import contextlib
import os
from contextlib import asynccontextmanager

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import MenuButtonWebApp, WebAppInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI

from yaft.analysis.qa_sql_tool import ReadOnlySQL
from yaft.api.routes import accounts as acc_routes
from yaft.api.routes import ask as ask_routes
from yaft.api.routes import budgets as bud_routes
from yaft.api.routes import categories as cat_routes
from yaft.api.routes import forecast as forecast_routes
from yaft.api.routes import goals as goal_routes
from yaft.api.routes import recurring as rec_routes
from yaft.api.routes import settings as set_routes
from yaft.api.routes import summary as sum_routes
from yaft.api.routes import transactions as tx_routes
from yaft.bot.auth import OwnerOnly
from yaft.bot.handlers.callbacks import handle_callback
from yaft.bot.handlers.commands import (
    cmd_ask,
    cmd_balance,
    cmd_forecast,
    cmd_help,
    cmd_list,
    cmd_start,
)
from yaft.bot.handlers.text import handle_text
from yaft.bot.handlers.voice import handle_voice
from yaft.config import get_settings
from yaft.db.session import make_engine, make_sessionmaker
from yaft.logging_setup import configure_logging, log
from yaft.pipeline.openrouter import OpenRouterClient
from yaft.scheduler import jobs as scheduler_jobs


def _apply_sqlite_pragmas(db_url: str) -> None:
    """Apply WAL + synchronous=NORMAL and run integrity_check on the SQLite file.

    WAL is persisted in the database header, so applying it once via a sync
    sqlite3 connection is sufficient — subsequent SQLAlchemy connections inherit
    it. Skips in-memory and non-sqlite URLs.
    """
    if not db_url.startswith("sqlite"):
        return
    path = db_url.split("///", 1)[-1]
    if not path or path == ":memory:":
        return
    import sqlite3
    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        rows = con.execute("PRAGMA integrity_check").fetchall()
        if rows and rows[0][0] != "ok":
            raise RuntimeError(f"sqlite integrity_check failed: {rows}")
    finally:
        con.close()


def make_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.bot_token or not settings.owner_tg_id:
        raise RuntimeError("BOT_TOKEN and OWNER_TG_ID must be set")
    _apply_sqlite_pragmas(settings.db_url)
    engine = make_engine(settings.db_url)
    Session = make_sessionmaker(engine)

    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    owner = OwnerOnly(settings.owner_tg_id)
    http_client = httpx.AsyncClient(timeout=15.0)

    sdk = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key or "missing",
    )
    llm = OpenRouterClient(sdk=sdk)
    read_only_sql = ReadOnlySQL(settings.db_url)
    if not settings.openrouter_api_key:
        log.warning(
            "OPENROUTER_API_KEY not set — voice and free-form text features will fail at runtime"
        )

    tz = getattr(settings, "timezone", "UTC") or "UTC"
    scheduler = AsyncIOScheduler(timezone=tz)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info("startup", owner_tg_id=settings.owner_tg_id)
        app.state.poll_task = asyncio.create_task(dp.start_polling(bot))
        if settings.public_https_url:
            try:
                await bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(
                        text="Dashboard",
                        web_app=WebAppInfo(url=settings.public_https_url + "/"),
                    )
                )
            except Exception as e:
                log.warning("set_chat_menu_button failed", error=str(e))
        # Bootstrap APScheduler jobs — non-fatal if any add_job fails
        try:
            scheduler.add_job(
                scheduler_jobs.materialize_recurring, "cron",
                hour=0, minute=5, args=[Session],
                id="materialize_recurring", replace_existing=True,
            )
            scheduler.add_job(
                scheduler_jobs.check_budget_alerts, "cron",
                minute=0, args=[Session],
                kwargs={"bot": bot, "owner_id": settings.owner_tg_id},
                id="budget_alerts", replace_existing=True,
            )
            scheduler.add_job(
                scheduler_jobs.fetch_fx_rates, "cron",
                hour=6, minute=0, args=[Session],
                id="fx", replace_existing=True,
            )
            scheduler.add_job(
                scheduler_jobs.weekly_coach, "cron",
                day_of_week="sun", hour=9, args=[Session],
                kwargs={"bot": bot, "owner_id": settings.owner_tg_id, "llm": llm},
                id="digest", replace_existing=True,
            )
            scheduler.add_job(
                scheduler_jobs.monthly_summary, "cron",
                day=1, hour=9, args=[Session],
                kwargs={"bot": bot, "owner_id": settings.owner_tg_id, "llm": llm},
                id="monthly_summary", replace_existing=True,
            )
            db_path = settings.db_url.split("///", 1)[-1]
            backup_dir = os.environ.get("BACKUP_DIR", "/var/lib/yaft/backups")
            rclone_remote = os.environ.get("BACKUP_RCLONE_REMOTE") or None
            scheduler.add_job(
                scheduler_jobs.backup, "cron",
                hour=3, minute=0, args=[Session],
                kwargs={
                    "db_path": db_path,
                    "out_dir": backup_dir,
                    "rclone_remote": rclone_remote,
                },
                id="backup", replace_existing=True,
            )
            scheduler.add_job(
                scheduler_jobs.heartbeat, "cron",
                hour=12, minute=0, args=[Session],
                kwargs={
                    "bot": bot,
                    "owner_id": settings.owner_tg_id,
                    "backup_dir": backup_dir,
                },
                id="heartbeat", replace_existing=True,
            )
            scheduler.start()
            app.state.scheduler = scheduler
            log.info("scheduler.started", jobs=len(scheduler.get_jobs()))
        except Exception as exc:
            log.warning("scheduler.start_failed", error=str(exc))
        yield
        log.info("shutdown")
        if getattr(app.state, "scheduler", None):
            app.state.scheduler.shutdown(wait=False)
        app.state.poll_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app.state.poll_task
        await http_client.aclose()
        await bot.session.close()
        await engine.dispose()

    fastapi_app = FastAPI(lifespan=lifespan)
    fastapi_app.state.engine = engine
    fastapi_app.state.session_maker = Session
    fastapi_app.state.llm = llm
    fastapi_app.state.read_only_sql = read_only_sql
    fastapi_app.include_router(ask_routes.router)
    fastapi_app.include_router(forecast_routes.router)
    fastapi_app.include_router(tx_routes.router)
    fastapi_app.include_router(acc_routes.router)
    fastapi_app.include_router(cat_routes.router)
    fastapi_app.include_router(sum_routes.router)
    fastapi_app.include_router(set_routes.router)
    fastapi_app.include_router(bud_routes.router)
    fastapi_app.include_router(goal_routes.router)
    fastapi_app.include_router(rec_routes.router)

    WEBAPP_DIR = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "webapp", "dist")
    )
    if os.path.isdir(WEBAPP_DIR):
        # Vite emits hash-suffixed filenames (e.g. index-DZlX_d_O.js) under
        # /assets/, so they're safe to cache for a year. index.html itself
        # must NOT be cached, otherwise updates never reach Telegram WebViews.
        from starlette.middleware.base import BaseHTTPMiddleware

        class _StaticCacheHeaders(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                response = await call_next(request)
                p = request.url.path
                if p.startswith("/assets/") or p.startswith("/app/assets/"):
                    response.headers["Cache-Control"] = (
                        "public, max-age=31536000, immutable"
                    )
                elif p in ("/", "/app/", "/index.html", "/app/index.html"):
                    response.headers["Cache-Control"] = "no-cache"
                return response

        fastapi_app.add_middleware(_StaticCacheHeaders)
        # Mount the SPA at /app for the long-standing path AND at / so Telegram
        # WebViews opening the bare host see content immediately (no redirect
        # that could drop the initData fragment in some clients).
        fastapi_app.mount(
            "/app",
            StaticFiles(directory=WEBAPP_DIR, html=True),
            name="webapp",
        )
        fastapi_app.mount(
            "/",
            StaticFiles(directory=WEBAPP_DIR, html=True),
            name="webapp_root",
        )

    @fastapi_app.get("/healthz")
    async def healthz():
        return {"ok": True}

    @dp.message(owner, Command("start"))
    async def _start(msg):
        await cmd_start(msg)

    @dp.message(owner, Command("help"))
    async def _help(msg):
        await cmd_help(msg)

    @dp.message(owner, Command("balance"))
    async def _balance(msg):
        async with Session() as s:
            await cmd_balance(msg, s)

    @dp.message(owner, Command("list"))
    async def _list(msg):
        async with Session() as s:
            await cmd_list(msg, s)

    @dp.message(owner, Command("ask"))
    async def _ask(msg):
        async with Session() as s:
            await cmd_ask(msg, s, llm=llm, db_url=settings.db_url)

    @dp.message(owner, Command("forecast"))
    async def _forecast(msg):
        async with Session() as s:
            await cmd_forecast(msg, s, llm=llm)

    @dp.message(owner, F.text)
    async def _text(msg):
        async with Session() as s:
            await handle_text(msg, s, http_client=http_client, llm=llm)

    @dp.message(owner, F.voice)
    async def _voice(msg):
        async with Session() as s:
            await handle_voice(msg, s, bot=bot, llm=llm, http_client=http_client)

    @dp.callback_query(owner, F.data.startswith("tx:"))
    async def _cb(cb):
        async with Session() as s:
            await handle_callback(cb, s, llm=llm, http_client=http_client)

    return fastapi_app

app = make_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("yaft.app:app", host="127.0.0.1", port=8080, reload=False)

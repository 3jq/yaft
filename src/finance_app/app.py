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

from finance_app.api.routes import accounts as acc_routes
from finance_app.api.routes import budgets as bud_routes
from finance_app.api.routes import categories as cat_routes
from finance_app.api.routes import goals as goal_routes
from finance_app.api.routes import recurring as rec_routes
from finance_app.api.routes import settings as set_routes
from finance_app.api.routes import summary as sum_routes
from finance_app.api.routes import transactions as tx_routes
from finance_app.bot.auth import OwnerOnly
from finance_app.bot.handlers.callbacks import handle_callback
from finance_app.bot.handlers.commands import cmd_balance, cmd_help, cmd_list, cmd_start
from finance_app.bot.handlers.text import handle_text
from finance_app.bot.handlers.voice import handle_voice
from finance_app.config import get_settings
from finance_app.db.session import make_engine, make_sessionmaker
from finance_app.logging_setup import configure_logging, log
from finance_app.pipeline.openrouter import OpenRouterClient
from finance_app.scheduler import jobs as scheduler_jobs


def make_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
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
                        web_app=WebAppInfo(url=settings.public_https_url + "/app/"),
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
                scheduler_jobs.weekly_digest_skeleton, "cron",
                day_of_week="sun", hour=9, args=[Session],
                kwargs={"bot": bot, "owner_id": settings.owner_tg_id},
                id="digest", replace_existing=True,
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
        fastapi_app.mount(
            "/app",
            StaticFiles(directory=WEBAPP_DIR, html=True),
            name="webapp",
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
    uvicorn.run("finance_app.app:app", host="127.0.0.1", port=8080, reload=False)

from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from fastapi import FastAPI
from openai import AsyncOpenAI

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

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info("startup", owner_tg_id=settings.owner_tg_id)
        app.state.poll_task = asyncio.create_task(dp.start_polling(bot))
        yield
        log.info("shutdown")
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

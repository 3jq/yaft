from __future__ import annotations

import asyncio
import contextlib

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from fastapi import FastAPI

from finance_app.bot.auth import OwnerOnly
from finance_app.bot.handlers.callbacks import handle_callback
from finance_app.bot.handlers.commands import cmd_balance, cmd_help, cmd_list, cmd_start
from finance_app.bot.handlers.text import handle_text
from finance_app.config import get_settings
from finance_app.db.session import make_engine, make_sessionmaker
from finance_app.logging_setup import configure_logging, log


def make_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.db_url)
    Session = make_sessionmaker(engine)

    fastapi_app = FastAPI()
    fastapi_app.state.engine = engine
    fastapi_app.state.session_maker = Session

    @fastapi_app.get("/healthz")
    async def healthz():
        return {"ok": True}

    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    owner = OwnerOnly(settings.owner_tg_id)
    http_client = httpx.AsyncClient(timeout=15.0)

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
            await handle_text(msg, s, http_client=http_client)

    @dp.callback_query(owner, F.data.startswith("tx:"))
    async def _cb(cb):
        async with Session() as s:
            await handle_callback(cb, s)

    @fastapi_app.on_event("startup")
    async def _startup() -> None:
        log.info("startup", owner_tg_id=settings.owner_tg_id)
        fastapi_app.state.poll_task = asyncio.create_task(dp.start_polling(bot))

    @fastapi_app.on_event("shutdown")
    async def _shutdown() -> None:
        log.info("shutdown")
        fastapi_app.state.poll_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await fastapi_app.state.poll_task
        await http_client.aclose()
        await bot.session.close()
        await engine.dispose()

    return fastapi_app

app = make_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("finance_app.app:app", host="127.0.0.1", port=8080, reload=False)

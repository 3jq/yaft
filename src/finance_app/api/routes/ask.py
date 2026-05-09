from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select

from finance_app.analysis.qa_sql_tool import ReadOnlySQL, schema_text
from finance_app.api.auth import require_owner
from finance_app.api.routes.transactions import _session
from finance_app.db.models import Setting

router = APIRouter(prefix="/api/ask", tags=["ask"])


class AskIn(BaseModel):
    question: str


class AskOut(BaseModel):
    answer: str


def _llm_singleton(request: Request):
    return request.app.state.llm


async def _build_context_text(session) -> str:
    rows = (await session.execute(select(Setting))).scalars().all()
    settings_map = {r.key: r.value for r in rows}
    base = settings_map.get("base_currency", "USD")
    tz = settings_map.get("timezone", "UTC")
    return (
        f"base_currency: {base}\n"
        f"timezone: {tz}\n"
        f"today: {dt.date.today().isoformat()}\n"
    )


@router.post("", response_model=AskOut)
async def ask(
    body: AskIn,
    request: Request,
    session=Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    llm = _llm_singleton(request)
    ro: ReadOnlySQL = request.app.state.read_only_sql
    context_text = await _build_context_text(session)
    answer = await llm.ask_with_sql(
        body.question,
        schema_text=schema_text(),
        sql_runner=ro.run_sql,
        context_text=context_text,
    )
    return AskOut(answer=answer)

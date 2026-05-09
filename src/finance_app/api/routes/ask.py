from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from finance_app.analysis.qa_sql_tool import ReadOnlySQL, schema_text
from finance_app.api.auth import require_owner

router = APIRouter(prefix="/api/ask", tags=["ask"])


class AskIn(BaseModel):
    question: str


class AskOut(BaseModel):
    answer: str


def _llm_singleton(request: Request):
    return request.app.state.llm


@router.post("", response_model=AskOut)
async def ask(body: AskIn, request: Request, _u=Depends(require_owner)):
    llm = _llm_singleton(request)
    ro: ReadOnlySQL = request.app.state.read_only_sql
    answer = await llm.ask_with_sql(
        body.question,
        schema_text=schema_text(),
        sql_runner=ro.run_sql,
    )
    return AskOut(answer=answer)

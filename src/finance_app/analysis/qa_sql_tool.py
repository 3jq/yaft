from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Defense-in-depth: only allow read statements.
_ALLOWED = re.compile(r"^\s*(WITH|SELECT)\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|REPLACE|DROP|ALTER|CREATE|ATTACH|DETACH|VACUUM|PRAGMA)\b",
    re.IGNORECASE,
)


class ReadOnlySQL:
    def __init__(self, db_url: str):
        # Use a separate engine so we can apply query_only PRAGMA per session.
        self._engine = create_async_engine(db_url, future=True)

    async def run_sql(self, query: str, *, limit: int = 1000) -> list[dict]:
        if not _ALLOWED.match(query):
            raise ValueError("only SELECT/WITH queries allowed")
        if _FORBIDDEN.search(query):
            raise ValueError("forbidden token in query")
        async with self._engine.connect() as conn:
            await conn.execute(text("PRAGMA query_only = 1"))
            result = await conn.execute(text(query))
            rows = result.mappings().fetchmany(limit)
            return [dict(r) for r in rows]

    async def aclose(self) -> None:
        await self._engine.dispose()


def schema_text() -> str:
    from finance_app.db.session import Base
    from sqlalchemy.schema import CreateTable
    import sqlalchemy.dialects.sqlite

    parts = []
    for tbl in Base.metadata.sorted_tables:
        parts.append(
            str(CreateTable(tbl).compile(dialect=sqlalchemy.dialects.sqlite.dialect()))
        )
    return "\n".join(parts)

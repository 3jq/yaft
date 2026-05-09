import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.db.session import Base, make_engine, make_sessionmaker


@pytest.fixture
async def session() -> AsyncSession:
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = make_sessionmaker(engine)
    async with Session() as s:
        yield s
    await engine.dispose()

from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models import Base


def create_engine(database_url: str) -> AsyncEngine:
    """Builds the async engine, creating the SQLite parent directory if the
    URL points at a file that lives in one."""
    if database_url.startswith("sqlite+aiosqlite:///"):
        path = database_url.removeprefix("sqlite+aiosqlite:///")
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)

    return create_async_engine(database_url, future=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(engine: AsyncEngine) -> None:
    """Creates any missing tables.

    Later phases add new tables (analysis, issues, metrics) which this picks up
    automatically. It does not alter existing columns; a real migration tool
    belongs here if the schema ever changes destructively.
    """
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

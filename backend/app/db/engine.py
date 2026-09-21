from pathlib import Path

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models import Base

logger = logging.getLogger(__name__)


def prepare_database_url(database_url: str) -> tuple[str, dict]:
    """Turns the URL a hosting provider hands out into one the async driver accepts.

    Managed Postgres gives `postgres://` or `postgresql://` URLs ending in
    `?sslmode=require`. SQLAlchemy needs the asyncpg driver named in the scheme,
    and asyncpg does not understand libpq's `sslmode` parameter at all - it
    fails at connect time with an unhelpful error - so that parameter is
    translated into the `ssl` argument asyncpg does take.
    """
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url.removeprefix("postgres://")

    url = make_url(database_url)

    if url.get_backend_name() != "postgresql":
        return database_url, {}

    query = dict(url.query)
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)

    connect_args: dict = {}
    if sslmode in {"require", "verify-ca", "verify-full"}:
        connect_args["ssl"] = True

    url = url.set(drivername="postgresql+asyncpg", query=query)
    return url.render_as_string(hide_password=False), connect_args


def create_engine(database_url: str) -> AsyncEngine:
    """Builds the async engine, creating the SQLite parent directory if the
    URL points at a file that lives in one."""
    if database_url.startswith("sqlite+aiosqlite:///"):
        path = database_url.removeprefix("sqlite+aiosqlite:///")
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        return create_async_engine(database_url, future=True)

    url, connect_args = prepare_database_url(database_url)
    # Serverless Postgres suspends idle databases and drops their connections;
    # pinging before use turns that into a quiet reconnect instead of an error
    # on the first request after a quiet period.
    return create_async_engine(
        url,
        future=True,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=300,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(engine: AsyncEngine) -> None:
    """Brings the database up to date with the models.

    `create_all` adds missing tables but silently ignores columns added to a
    table that already exists, which surfaces later as a baffling
    "no such column" in the middle of a request. Each analysis phase adds
    nullable columns to `speech_analyses`, so those are reconciled here too.
    """
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_add_missing_columns)


def _add_missing_columns(connection) -> None:
    """Adds columns the models declare but the database lacks.

    Only safe additions are handled: a new nullable column with no default.
    Renames, drops and type changes are deliberately out of scope - those need
    a real migration tool, and pretending otherwise would lose data.
    """
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue

        present = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue
            if not column.nullable:
                logger.error(
                    "Column %s.%s is missing and cannot be added automatically "
                    "because it is NOT NULL. The database schema is out of "
                    "date; recreate it or add a migration.",
                    table.name, column.name,
                )
                continue

            ddl = column.type.compile(connection.dialect)
            connection.execute(
                text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl}')
            )
            logger.info("Added missing column %s.%s", table.name, column.name)

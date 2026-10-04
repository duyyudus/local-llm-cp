from __future__ import annotations

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from common.config import Settings

_ENGINES: dict[str, AsyncEngine] = {}
_SESSION_FACTORIES: dict[str, async_sessionmaker[AsyncSession]] = {}


def ensure_sqlite_dir(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)


def make_engine(settings: Settings) -> AsyncEngine:
    engine = _ENGINES.get(settings.database_url)
    if engine is None:
        ensure_sqlite_dir(settings.database_url)
        engine = create_async_engine(settings.database_url)
        if engine.dialect.name == "sqlite":
            event.listen(engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
        _ENGINES[settings.database_url] = engine
    return engine


def make_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    factory = _SESSION_FACTORIES.get(settings.database_url)
    if factory is None:
        factory = async_sessionmaker(make_engine(settings), expire_on_commit=False)
        _SESSION_FACTORIES[settings.database_url] = factory
    return factory


def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

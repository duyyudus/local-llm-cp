from __future__ import annotations

import contextlib
import os
import signal
import socket
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api_server.app.main import create_app
from api_server.app.remote.local import LocalExecutor
from api_server.app.runtime import Runtime
from common.config import Settings
from common.db.models import Base

STUB_SERVER = str(Path(__file__).parent / "stub_server.py")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def profile_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "stub",
        "executable_path": STUB_SERVER,
        "host": "127.0.0.1",
        "port": free_port(),
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db",
        remote_mode="local",
        remote_state_dir=str(tmp_path / "state"),
        stop_timeout_seconds=3,
    )


@pytest.fixture()
async def session_factory(settings: Settings):
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture()
async def runtime(settings: Settings, session_factory):
    runtime = Runtime(settings, session_factory, executor=LocalExecutor())
    yield runtime
    # Never leave stub servers behind, whatever the test did.
    for run in list(runtime.live.values()):
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(run.pid, signal.SIGKILL)
    await runtime.stop()


@pytest.fixture()
async def client(settings: Settings, session_factory, runtime: Runtime):
    app = create_app(settings)
    app.state.session_factory = session_factory
    app.state.runtime = runtime
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

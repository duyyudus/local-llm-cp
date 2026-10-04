from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api_server.app.api.routers import router
from api_server.app.remote.executor import RemoteUnavailableError
from api_server.app.runtime import Runtime
from common.config import Settings, load_settings
from common.db.session import make_session_factory
from common.logging import setup_logging


@asynccontextmanager
async def _lifespan(api: FastAPI) -> AsyncIterator[None]:
    settings: Settings = api.state.settings
    setup_logging(settings)
    session_factory = make_session_factory(settings)
    api.state.session_factory = session_factory
    runtime = Runtime(settings, session_factory)
    api.state.runtime = runtime
    await runtime.start()
    try:
        yield
    finally:
        await runtime.stop()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    api = FastAPI(title="Local LLM Control Panel API", version="0.1.0", lifespan=_lifespan)
    api.state.settings = settings
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.api_cors_origin_regex or None,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @api.exception_handler(RemoteUnavailableError)
    async def remote_unavailable(_request: Request, exc: RemoteUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": f"GPU host unavailable: {exc}"})

    api.include_router(router)
    return api


app = create_app()

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from sqlalchemy import select

from api_server.app.api.dependencies import RuntimeDep, SessionDep
from api_server.app.api.sse import KEEPALIVE, KEEPALIVE_SECONDS, sse_event, sse_response
from api_server.app.db import get_session_factory
from api_server.app.remote.executor import RemoteUnavailableError
from api_server.app.schemas import ProfileRead
from api_server.app.services import profiles as profile_service
from api_server.app.services import runs as run_service
from common.db.models import Run

router = APIRouter()


@router.post("/profiles/{profile_id}/start", response_model=ProfileRead)
async def start_profile(profile_id: str, session: SessionDep, runtime: RuntimeDep) -> ProfileRead:
    profile = await profile_service.get_profile(session, profile_id)
    await run_service.start_profile(session, runtime, profile)
    return await profile_service.read_profile(session, runtime, profile)


@router.post("/profiles/{profile_id}/stop", response_model=ProfileRead)
async def stop_profile(profile_id: str, session: SessionDep, runtime: RuntimeDep) -> ProfileRead:
    profile = await profile_service.get_profile(session, profile_id)
    await run_service.stop_profile(session, runtime, profile)
    return await profile_service.read_profile(session, runtime, profile)


@router.get("/profiles/{profile_id}/logs/stream")
async def stream_logs(profile_id: str, request: Request, runtime: RuntimeDep):
    # The stream outlives a request-scoped session, so look the run up with a short one.
    async with get_session_factory(request)() as session:
        run = await session.scalar(
            select(Run).where(Run.profile_id == profile_id).order_by(Run.started_at.desc())
        )
    if run is not None and run.stopped_at is not None:
        with contextlib.suppress(RemoteUnavailableError):
            await runtime.logs.load_backlog(profile_id, run.log_path)
    channel = runtime.logs.channel(profile_id)

    async def generate() -> AsyncIterator[str]:
        generation: int | None = None
        seq = 0
        while True:
            # Grab the event before reading so a line appended in between still wakes us.
            event = channel.event
            if channel.generation != generation:
                generation = channel.generation
                seq = channel.first_seq
                yield sse_event("reset", {})
            lines, seq = channel.since(seq)
            if lines:
                yield sse_event("lines", {"lines": lines})
                continue
            try:
                await asyncio.wait_for(event.wait(), KEEPALIVE_SECONDS)
            except TimeoutError:
                yield KEEPALIVE

    return sse_response(generate())

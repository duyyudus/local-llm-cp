from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from api_server.app.api.dependencies import RuntimeDep
from api_server.app.api.sse import KEEPALIVE, KEEPALIVE_SECONDS, sse_event, sse_response
from api_server.app.schemas import DirListingRead, GpuRead, HostRead

router = APIRouter()


@router.get("/host", response_model=HostRead)
async def host(runtime: RuntimeDep) -> HostRead:
    return HostRead(**asdict(runtime.executor.state), gpu_error=runtime.gpu.error)


@router.get("/host/browse", response_model=DirListingRead)
async def browse(runtime: RuntimeDep, path: str = "~") -> DirListingRead:
    try:
        listing = await runtime.executor.listdir(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Cannot list {path}: {exc}") from exc
    return DirListingRead.model_validate(asdict(listing))


@router.get("/gpu", response_model=GpuRead)
async def gpu(runtime: RuntimeDep) -> GpuRead:
    return GpuRead(error=runtime.gpu.error, snapshot=runtime.gpu.latest)


@router.get("/gpu/stream")
async def gpu_stream(runtime: RuntimeDep):
    sampler = runtime.gpu

    async def generate() -> AsyncIterator[str]:
        seq = sampler.first_seq
        error: str | None = None
        first = True
        while True:
            # Grab the event before reading so an update in between still wakes us.
            event = sampler.event
            snapshots, seq = sampler.since(seq)
            if first:
                yield sse_event("history", {"snapshots": snapshots})
                first = False
            else:
                for snapshot in snapshots:
                    yield sse_event("snapshot", snapshot)
            if sampler.error != error:
                error = sampler.error
                yield sse_event("status", {"error": error})
            try:
                await asyncio.wait_for(event.wait(), KEEPALIVE_SECONDS)
            except TimeoutError:
                yield KEEPALIVE

    return sse_response(generate())

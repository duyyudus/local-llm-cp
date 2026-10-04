from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from api_server.app.api.dependencies import RuntimeDep
from api_server.app.api.sse import KEEPALIVE, KEEPALIVE_SECONDS, sse_event, sse_response
from api_server.app.remote.power import ShutdownError, shutdown
from api_server.app.remote.samples import SampleHistory
from api_server.app.schemas import DirListingRead, GpuRead, HostRead, SystemRead

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


@router.post("/host/shutdown", status_code=204)
async def shutdown_host(runtime: RuntimeDep) -> None:
    try:
        settings = runtime.settings
        await shutdown(runtime.executor, settings.host_shutdown_command, settings.gpu_ssh_password)
    except ShutdownError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/gpu", response_model=GpuRead)
async def gpu(runtime: RuntimeDep) -> GpuRead:
    return GpuRead(error=runtime.gpu.error, snapshot=runtime.gpu.latest)


@router.get("/system", response_model=SystemRead)
async def system(runtime: RuntimeDep) -> SystemRead:
    return SystemRead(error=runtime.system.error, snapshot=runtime.system.latest)


@router.get("/host/stream")
async def host_stream(runtime: RuntimeDep):
    # GPU and system samples share one stream so a browser tab holds a single connection.
    feeds: list[tuple[str, SampleHistory]] = [("gpu", runtime.gpu), ("system", runtime.system)]

    async def generate() -> AsyncIterator[str]:
        with runtime.activity.stream():
            seqs = {name: sampler.first_seq for name, sampler in feeds}
            errors: dict[str, str | None] = {name: None for name, _ in feeds}
            first = True
            while True:
                # Grab the events before reading so an update in between still wakes us.
                events = [sampler.event for _, sampler in feeds]
                for name, sampler in feeds:
                    snapshots, seqs[name] = sampler.since(seqs[name])
                    if first:
                        yield sse_event(f"{name}_history", {"snapshots": snapshots})
                    else:
                        for snapshot in snapshots:
                            yield sse_event(f"{name}_snapshot", snapshot)
                    if sampler.error != errors[name]:
                        errors[name] = sampler.error
                        yield sse_event(f"{name}_status", {"error": sampler.error})
                first = False
                waiters = [asyncio.create_task(event.wait()) for event in events]
                try:
                    done, _ = await asyncio.wait(
                        waiters, timeout=KEEPALIVE_SECONDS, return_when=asyncio.FIRST_COMPLETED
                    )
                finally:
                    for waiter in waiters:
                        waiter.cancel()
                if not done:
                    yield KEEPALIVE

    return sse_response(generate())

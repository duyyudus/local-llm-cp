from __future__ import annotations

import asyncio

from api_server.app.remote.activity import Activity
from api_server.app.remote.executor import RemoteUnavailableError
from api_server.app.remote.gpu import GpuSampler


async def test_activity_follows_requests_and_open_streams() -> None:
    activity = Activity(idle_seconds=0.05)
    assert not activity.active
    activity.touch()
    assert activity.active
    await asyncio.sleep(0.1)
    assert not activity.active

    with activity.stream():
        await asyncio.sleep(0.1)
        assert activity.active
    # Closing the last stream starts the idle countdown rather than pausing at once.
    assert activity.active
    await asyncio.sleep(0.1)
    assert not activity.active


def test_activity_without_idle_timeout_never_pauses() -> None:
    assert Activity().active


class CountingOfflineExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, command: str, timeout: float = 15.0, input: str | None = None):
        self.calls += 1
        raise RemoteUnavailableError("connection refused")


async def test_sampler_leaves_the_host_alone_until_a_dashboard_shows_up() -> None:
    executor = CountingOfflineExecutor()
    activity = Activity(idle_seconds=30)
    sampler = GpuSampler(
        executor,  # type: ignore[arg-type]
        history_samples=2,
        process_interval=0.01,
        resolve_pid=lambda _pid: None,
        activity=activity,
    )
    sampler.start()
    try:
        await asyncio.sleep(0.1)
        assert executor.calls == 0
        activity.touch()
        await asyncio.sleep(0.1)
        assert executor.calls > 0
        assert sampler.error == "connection refused"
    finally:
        await sampler.close()


async def test_only_dashboard_requests_count_as_activity(client, runtime) -> None:
    runtime.activity = Activity(idle_seconds=30)
    await client.get("/ready")
    await client.get("/health")
    assert not runtime.activity.active
    await client.get("/host")
    assert runtime.activity.active

from __future__ import annotations

import asyncio

from api_server.app.remote.local import LocalExecutor
from api_server.app.remote.system import (
    SystemSampler,
    cpu_percent,
    parse_info,
    parse_rss,
    parse_sample,
)

LINE = (
    "cpu  1000 0 500 8000 500 0 0 0 0 0 "
    "| MemTotal:65536000 MemAvailable:16384000 SwapTotal:8388608 SwapFree:4194304"
)


def test_parse_info() -> None:
    assert parse_info("32\nmodel name\t: AMD Ryzen 9 5950X 16-Core Processor\n") == (
        32,
        "AMD Ryzen 9 5950X 16-Core Processor",
    )
    assert parse_info("8\n") == (8, "")
    assert parse_info("") is None
    assert parse_info("grep: /proc/cpuinfo: No such file or directory") is None


def test_parse_sample_and_cpu_percent() -> None:
    sample = parse_sample(LINE)
    assert sample is not None
    times, memory = sample
    # iowait counts as idle.
    assert times == (1500, 10000)
    assert memory == {
        "MemTotal": 64000.0,
        "MemAvailable": 16000.0,
        "SwapTotal": 8192.0,
        "SwapFree": 4096.0,
    }
    assert cpu_percent(times, (1750, 10500)) == 50.0
    assert cpu_percent(times, times) is None
    assert parse_sample("cpu0 1 2 3 4 | MemTotal:1 MemAvailable:1") is None
    assert parse_sample("cpu  1 2 3 4 5 |") is None
    assert parse_sample("") is None


def test_parse_rss() -> None:
    assert parse_rss("4242 2097152\nnoise\n77 1024\n") == {4242: 2048.0, 77: 1.0}


def test_publish_attributes_memory_to_profiles() -> None:
    sampler = SystemSampler(
        executor=None,  # type: ignore[arg-type]
        history_samples=2,
        process_interval=1,
        live_processes=lambda: [(4242, "prf_1", "qwen"), (99, "prf_2", "gone")],
    )
    sampler._rss = {4242: 2048.0, 77: 1.0}
    _, memory = parse_sample(LINE)  # type: ignore[misc]
    sampler.publish(32, "Ryzen", 50.0, memory)
    snapshot = sampler.latest
    assert snapshot is not None
    del snapshot["ts"]
    assert snapshot == {
        "cpu_name": "Ryzen",
        "cpu_threads": 32,
        "cpu_utilization_pct": 50.0,
        "memory_used_mb": 48000.0,
        "memory_total_mb": 64000.0,
        "swap_used_mb": 4096.0,
        "swap_total_mb": 8192.0,
        "processes": [
            {"pid": 4242, "rss_mb": 2048.0, "profile_id": "prf_1", "profile_name": "qwen"}
        ],
    }


async def test_sampler_reads_the_local_host() -> None:
    sampler = SystemSampler(
        LocalExecutor(), history_samples=5, process_interval=1, live_processes=lambda: []
    )
    sampler.start()
    try:
        async with asyncio.timeout(10):
            while sampler.latest is None:
                await sampler.event.wait()
    finally:
        await sampler.close()
    snapshot = sampler.latest
    assert sampler.error is None
    assert snapshot["cpu_threads"] >= 1
    assert 0 <= snapshot["cpu_utilization_pct"] <= 100
    assert 0 < snapshot["memory_used_mb"] <= snapshot["memory_total_mb"]


async def test_system_endpoint(client) -> None:
    assert (await client.get("/system")).json() == {"error": None, "snapshot": None}

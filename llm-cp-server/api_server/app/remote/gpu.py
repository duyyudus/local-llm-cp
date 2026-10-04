from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from typing import Any

from api_server.app.remote.executor import RemoteExecutor, RemoteUnavailableError
from api_server.app.remote.samples import SampleHistory

GPU_FIELDS = (
    "index,uuid,name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw"
)
GPU_QUERY = f"nvidia-smi --query-gpu={GPU_FIELDS} --format=csv,noheader,nounits"
APPS_QUERY = (
    "nvidia-smi --query-compute-apps=pid,used_memory,gpu_uuid --format=csv,noheader,nounits"
)
RETRY_SECONDS = 5.0

PidResolver = Callable[[int], tuple[str, str] | None]


def _number(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        # nvidia-smi prints "[N/A]" or "[Not Supported]" for unavailable readings.
        return None


def parse_gpu_line(line: str) -> dict[str, Any] | None:
    parts = [part.strip() for part in line.split(",")]
    if len(parts) != 8 or not parts[0].isdigit():
        return None
    return {
        "index": int(parts[0]),
        "uuid": parts[1],
        "name": parts[2],
        "memory_used_mb": _number(parts[3]),
        "memory_total_mb": _number(parts[4]),
        "utilization_pct": _number(parts[5]),
        "temperature_c": _number(parts[6]),
        "power_w": _number(parts[7]),
    }


def parse_apps(output: str) -> dict[str, list[tuple[int, float | None]]]:
    apps: dict[str, list[tuple[int, float | None]]] = {}
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 3 or not parts[0].isdigit():
            continue
        apps.setdefault(parts[2], []).append((int(parts[0]), _number(parts[1])))
    return apps


class GpuSampler(SampleHistory):
    """Streams `nvidia-smi -l 1` from the GPU host and keeps a short history."""

    def __init__(
        self,
        executor: RemoteExecutor,
        *,
        history_samples: int,
        process_interval: float,
        resolve_pid: PidResolver,
    ) -> None:
        super().__init__(history_samples)
        self._executor = executor
        self._process_interval = process_interval
        self._resolve_pid = resolve_pid
        self._apps: dict[str, list[tuple[int, float | None]]] = {}
        self._tasks: list[asyncio.Task[None]] = []

    def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._sample_gpus()),
            asyncio.create_task(self._sample_apps()),
        ]

    async def close(self) -> None:
        tasks, self._tasks = self._tasks, []
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    def publish(self, gpus: list[dict[str, Any]]) -> None:
        for gpu in gpus:
            processes = []
            for pid, used_mb in self._apps.get(gpu["uuid"], []):
                owner = self._resolve_pid(pid)
                processes.append(
                    {
                        "pid": pid,
                        "used_mb": used_mb,
                        "profile_id": owner[0] if owner else None,
                        "profile_name": owner[1] if owner else None,
                    }
                )
            gpu["processes"] = processes
        self._append({"ts": round(time.time() * 1000), "gpus": gpus})

    async def _sample_gpus(self) -> None:
        while True:
            try:
                probe = await self._executor.run(GPU_QUERY)
                count = len([line for line in probe.stdout.splitlines() if parse_gpu_line(line)])
                if not probe.ok or count == 0:
                    detail = probe.stderr.strip() or probe.stdout.strip() or "no GPUs reported"
                    self._set_error(f"nvidia-smi failed: {detail}")
                else:
                    pending: list[dict[str, Any]] = []
                    async with contextlib.aclosing(
                        self._executor.stream(f"{GPU_QUERY} -l 1")
                    ) as lines:
                        async for line in lines:
                            gpu = parse_gpu_line(line)
                            if gpu is None:
                                continue
                            pending.append(gpu)
                            if len(pending) >= count:
                                self.publish(pending)
                                pending = []
                    self._set_error("nvidia-smi stream ended")
            except RemoteUnavailableError as exc:
                self._set_error(str(exc))
            await asyncio.sleep(RETRY_SECONDS)

    async def _sample_apps(self) -> None:
        while True:
            try:
                result = await self._executor.run(APPS_QUERY)
                if result.ok:
                    self._apps = parse_apps(result.stdout)
            except RemoteUnavailableError:
                self._apps = {}
            await asyncio.sleep(self._process_interval)

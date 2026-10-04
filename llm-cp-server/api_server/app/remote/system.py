from __future__ import annotations

import asyncio
import contextlib
import shlex
import time
from collections.abc import Callable
from typing import Any

from api_server.app.remote.executor import RemoteExecutor, RemoteUnavailableError, bash
from api_server.app.remote.samples import SampleHistory

INFO_QUERY = bash("grep -c ^processor /proc/cpuinfo; grep -m1 'model name' /proc/cpuinfo")
# One line per second: the aggregate /proc/stat counters, then the /proc/meminfo fields in kB.
SAMPLE_SCRIPT = """
while :; do
  read -r cpu < /proc/stat || exit 1
  mem=
  while read -r key value _; do
    case $key in
      MemTotal:|MemAvailable:|SwapTotal:|SwapFree:) mem="$mem $key$value" ;;
    esac
  done < /proc/meminfo
  echo "$cpu |$mem"
  sleep 1
done
"""
RSS_SCRIPT = """
for pid in {pids}; do
  while read -r key value _; do
    if [ "$key" = VmRSS: ]; then echo "$pid $value"; fi
  done < /proc/$pid/status
done 2>/dev/null
"""
RETRY_SECONDS = 5.0

CpuTimes = tuple[int, int]
LiveProcesses = Callable[[], list[tuple[int, str, str]]]


def parse_info(output: str) -> tuple[int, str] | None:
    lines = output.splitlines()
    if not lines or not lines[0].strip().isdigit() or int(lines[0]) == 0:
        return None
    # ARM hosts have no "model name" line.
    name = lines[1].partition(":")[2].strip() if len(lines) > 1 else ""
    return int(lines[0]), name


def parse_sample(line: str) -> tuple[CpuTimes, dict[str, float]] | None:
    """Return (busy, total) jiffies since boot and the meminfo fields in MB."""
    cpu, _, mem = line.partition("|")
    fields = cpu.split()
    if len(fields) < 5 or fields[0] != "cpu" or not all(f.isdigit() for f in fields[1:]):
        return None
    # user nice system idle iowait irq softirq steal; guest time is already inside user.
    times = [int(field) for field in fields[1:9]]
    idle = times[3] + (times[4] if len(times) > 4 else 0)
    memory: dict[str, float] = {}
    for item in mem.split():
        key, _, value = item.partition(":")
        if value.isdigit():
            memory[key] = int(value) / 1024
    if "MemTotal" not in memory or "MemAvailable" not in memory:
        return None
    return (sum(times) - idle, sum(times)), memory


def cpu_percent(previous: CpuTimes, current: CpuTimes) -> float | None:
    total = current[1] - previous[1]
    if total <= 0:
        return None
    return round(max(0.0, min(100.0, (current[0] - previous[0]) / total * 100)), 1)


def parse_rss(output: str) -> dict[int, float]:
    rss: dict[int, float] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            rss[int(parts[0])] = int(parts[1]) / 1024
    return rss


class SystemSampler(SampleHistory):
    """Streams CPU and memory usage from /proc on the GPU host and keeps a short history."""

    def __init__(
        self,
        executor: RemoteExecutor,
        *,
        history_samples: int,
        process_interval: float,
        live_processes: LiveProcesses,
    ) -> None:
        super().__init__(history_samples)
        self._executor = executor
        self._process_interval = process_interval
        self._live_processes = live_processes
        self._rss: dict[int, float] = {}
        self._tasks: list[asyncio.Task[None]] = []

    def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._sample_system()),
            asyncio.create_task(self._sample_rss()),
        ]

    async def close(self) -> None:
        tasks, self._tasks = self._tasks, []
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    def publish(
        self, threads: int, name: str, utilization_pct: float | None, memory: dict[str, float]
    ) -> None:
        swap_total = memory.get("SwapTotal", 0.0)
        snapshot: dict[str, Any] = {
            "ts": round(time.time() * 1000),
            "cpu_name": name,
            "cpu_threads": threads,
            "cpu_utilization_pct": utilization_pct,
            "memory_used_mb": round(memory["MemTotal"] - memory["MemAvailable"], 1),
            "memory_total_mb": round(memory["MemTotal"], 1),
            "swap_used_mb": round(swap_total - memory.get("SwapFree", 0.0), 1),
            "swap_total_mb": round(swap_total, 1),
            "processes": [
                {
                    "pid": pid,
                    "rss_mb": round(self._rss[pid], 1),
                    "profile_id": profile_id,
                    "profile_name": profile_name,
                }
                for pid, profile_id, profile_name in self._live_processes()
                if pid in self._rss
            ],
        }
        self._append(snapshot)

    async def _sample_system(self) -> None:
        while True:
            try:
                info = parse_info((await self._executor.run(INFO_QUERY)).stdout)
                if info is None:
                    self._set_error("cannot read /proc/cpuinfo on the host")
                else:
                    previous: CpuTimes | None = None
                    async with contextlib.aclosing(
                        self._executor.stream(bash(SAMPLE_SCRIPT))
                    ) as lines:
                        async for line in lines:
                            sample = parse_sample(line)
                            if sample is None:
                                continue
                            times, memory = sample
                            # Usage is a rate, so the first reading only sets the baseline.
                            if previous is not None:
                                self.publish(*info, cpu_percent(previous, times), memory)
                            previous = times
                    self._set_error("system stats stream ended")
            except RemoteUnavailableError as exc:
                self._set_error(str(exc))
            await asyncio.sleep(RETRY_SECONDS)

    async def _sample_rss(self) -> None:
        while True:
            pids = [pid for pid, _, _ in self._live_processes()]
            try:
                if pids:
                    script = RSS_SCRIPT.format(pids=" ".join(shlex.quote(str(p)) for p in pids))
                    self._rss = parse_rss((await self._executor.run(bash(script))).stdout)
                else:
                    self._rss = {}
            except RemoteUnavailableError:
                self._rss = {}
            await asyncio.sleep(self._process_interval)

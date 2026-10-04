from __future__ import annotations

import asyncio
import contextlib
import shlex
from collections import deque
from itertools import islice

from api_server.app.remote.executor import (
    RemoteExecutor,
    RemoteUnavailableError,
    bash,
    clean_line,
)

RETRY_SECONDS = 3.0


class LogChannel:
    """Bounded line buffer for one profile that SSE subscribers read by sequence number."""

    def __init__(self, max_lines: int) -> None:
        self._lines: deque[str] = deque(maxlen=max_lines)
        self.next_seq = 0
        # Bumped whenever the buffer restarts (a new launch), so subscribers clear their view.
        self.generation = 0
        self.event = asyncio.Event()

    @property
    def first_seq(self) -> int:
        return self.next_seq - len(self._lines)

    @property
    def empty(self) -> bool:
        return not self._lines

    def _notify(self) -> None:
        event, self.event = self.event, asyncio.Event()
        event.set()

    def append(self, line: str) -> None:
        self._lines.append(line)
        self.next_seq += 1
        self._notify()

    def reset(self) -> None:
        self._lines.clear()
        self.generation += 1
        self._notify()

    def since(self, seq: int, limit: int = 500) -> tuple[list[str], int]:
        start = max(seq, self.first_seq)
        offset = start - self.first_seq
        lines = list(islice(self._lines, offset, offset + limit))
        return lines, start + len(lines)


class LogHub:
    """Keeps one `tail -F` per running profile and fans its lines out to subscribers."""

    def __init__(self, executor: RemoteExecutor, max_lines: int, backlog_lines: int) -> None:
        self._executor = executor
        self._max_lines = max_lines
        self._backlog_lines = backlog_lines
        self._channels: dict[str, LogChannel] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._retired: set[asyncio.Task[None]] = set()

    def channel(self, profile_id: str) -> LogChannel:
        channel = self._channels.get(profile_id)
        if channel is None:
            channel = LogChannel(self._max_lines)
            self._channels[profile_id] = channel
        return channel

    def start_tail(self, profile_id: str, log_path: str, *, fresh: bool = False) -> None:
        self.stop_tail(profile_id)
        channel = self.channel(profile_id)
        if fresh:
            channel.reset()
        self._tasks[profile_id] = asyncio.create_task(self._tail(channel, log_path))

    def ensure_tail(self, profile_id: str, log_path: str) -> None:
        task = self._tasks.get(profile_id)
        if task is None or task.done():
            self.start_tail(profile_id, log_path)

    def stop_tail(self, profile_id: str, *, delay: float = 0.0) -> None:
        """Stop following the log. A delay lets the last lines of a dying process arrive."""
        task = self._tasks.pop(profile_id, None)
        if task is None:
            return
        if delay <= 0:
            task.cancel()
            return
        self._retired.add(task)
        task.add_done_callback(self._retired.discard)
        asyncio.get_running_loop().call_later(delay, task.cancel)

    async def load_backlog(self, profile_id: str, log_path: str) -> None:
        """Fill an empty channel from the log of a run that is no longer followed."""
        channel = self.channel(profile_id)
        if profile_id in self._tasks or not channel.empty:
            return
        generation = channel.generation
        result = await self._executor.run(
            bash(f"tail -n {self._backlog_lines} {shlex.quote(log_path)} 2>/dev/null")
        )
        if profile_id in self._tasks or channel.generation != generation or not channel.empty:
            return
        for line in result.stdout.splitlines():
            channel.append(clean_line(line))

    def forget(self, profile_id: str) -> None:
        self.stop_tail(profile_id)
        self._channels.pop(profile_id, None)

    async def close(self) -> None:
        tasks = [*self._tasks.values(), *self._retired]
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _tail(self, channel: LogChannel, log_path: str) -> None:
        quoted = shlex.quote(log_path)
        next_line: int | None = None
        while True:
            try:
                if next_line is None:
                    result = await self._executor.run(
                        bash(f"wc -l < {quoted} 2>/dev/null || echo 0")
                    )
                    total = int(result.stdout.strip() or 0)
                    next_line = max(1, total - self._backlog_lines + 1)
                # Resuming from an absolute line number avoids duplicates after a reconnect.
                command = f"tail -n +{next_line} -F {quoted} 2>/dev/null"
                async with contextlib.aclosing(self._executor.stream(command)) as lines:
                    async for line in lines:
                        channel.append(line)
                        next_line += 1
            except (RemoteUnavailableError, ValueError):
                pass
            await asyncio.sleep(RETRY_SECONDS)

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Iterator


class Activity:
    """Tracks whether a dashboard is watching, so host polling can pause when none is."""

    def __init__(self, idle_seconds: float = 0.0) -> None:
        # Zero disables the pause: the host is polled all the time.
        self._idle_seconds = idle_seconds
        self._last_seen: float | None = None
        self._streams = 0
        self._wake = asyncio.Event()

    @property
    def active(self) -> bool:
        if self._idle_seconds <= 0 or self._streams > 0:
            return True
        if self._last_seen is None:
            return False
        return time.monotonic() - self._last_seen < self._idle_seconds

    def touch(self) -> None:
        self._last_seen = time.monotonic()
        self._wake.set()

    @contextlib.contextmanager
    def stream(self) -> Iterator[None]:
        """Count an open SSE stream as activity for as long as it lasts."""
        self._streams += 1
        self._wake.set()
        try:
            yield
        finally:
            self._streams -= 1
            self.touch()

    async def wait(self) -> None:
        while not self.active:
            self._wake.clear()
            await self._wake.wait()

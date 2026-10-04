from __future__ import annotations

import asyncio
from collections import deque
from typing import Any

Snapshot = dict[str, Any]


class SampleHistory:
    """A bounded, sequence-numbered history of snapshots that SSE streams follow."""

    def __init__(self, history_samples: int) -> None:
        self._history: deque[Snapshot] = deque(maxlen=history_samples)
        self.next_seq = 0
        self.error: str | None = None
        self.event = asyncio.Event()

    @property
    def first_seq(self) -> int:
        return self.next_seq - len(self._history)

    @property
    def latest(self) -> Snapshot | None:
        return self._history[-1] if self._history else None

    def since(self, seq: int) -> tuple[list[Snapshot], int]:
        start = max(seq, self.first_seq)
        return list(self._history)[start - self.first_seq :], self.next_seq

    def _notify(self) -> None:
        event, self.event = self.event, asyncio.Event()
        event.set()

    def _set_error(self, message: str | None) -> None:
        if message != self.error:
            self.error = message
            self._notify()

    def _append(self, snapshot: Snapshot) -> None:
        self._history.append(snapshot)
        self.next_seq += 1
        self.error = None
        self._notify()

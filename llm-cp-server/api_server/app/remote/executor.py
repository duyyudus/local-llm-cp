from __future__ import annotations

import re
import shlex
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


class RemoteUnavailableError(Exception):
    """The GPU host cannot be reached or the command channel broke."""


@dataclass(frozen=True)
class CommandResult:
    exit_status: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_status == 0


@dataclass(frozen=True)
class ConnectionState:
    mode: str
    target: str
    connected: bool
    error: str | None = None


@dataclass(frozen=True)
class DirEntry:
    name: str
    is_dir: bool
    size: int | None = None


@dataclass(frozen=True)
class DirListing:
    path: str
    parent: str | None
    entries: list[DirEntry]


class RemoteExecutor(Protocol):
    @property
    def state(self) -> ConnectionState: ...

    async def close(self) -> None: ...

    async def run(
        self, command: str, timeout: float = 15.0, input: str | None = None
    ) -> CommandResult:
        """Run a shell command to completion on the GPU host, feeding `input` to its stdin."""

    def stream(self, command: str) -> AsyncIterator[str]:
        """Yield output lines of a long-running command; closing the iterator kills it."""

    async def listdir(self, path: str) -> DirListing: ...


def bash(script: str) -> str:
    return f"bash -c {shlex.quote(script)}"


def clean_line(raw: str) -> str:
    """Drop the line ending, terminal colour codes and carriage-return overwrites."""
    line = raw.rstrip("\r\n")
    if "\r" in line:
        segments = [segment for segment in line.split("\r") if segment]
        line = segments[-1] if segments else ""
    return ANSI_ESCAPE.sub("", line)


def sort_entries(entries: list[DirEntry]) -> list[DirEntry]:
    return sorted(entries, key=lambda entry: (not entry.is_dir, entry.name.lower()))

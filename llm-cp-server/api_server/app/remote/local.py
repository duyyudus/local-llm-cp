from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from collections.abc import AsyncIterator
from pathlib import Path

from api_server.app.remote.executor import (
    CommandResult,
    ConnectionState,
    DirEntry,
    DirListing,
    RemoteUnavailableError,
    clean_line,
    sort_entries,
)


class LocalExecutor:
    """Runs commands on this machine. Used for development, tests and same-box installs."""

    @property
    def state(self) -> ConnectionState:
        return ConnectionState(mode="local", target="localhost", connected=True)

    async def close(self) -> None:
        return None

    async def run(self, command: str, timeout: float = 15.0) -> CommandResult:
        process = await asyncio.create_subprocess_exec(
            "bash",
            "-c",
            command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
        except TimeoutError as exc:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            raise RemoteUnavailableError(f"Command timed out after {timeout:.0f}s") from exc
        return CommandResult(
            exit_status=process.returncode or 0,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
        )

    async def stream(self, command: str) -> AsyncIterator[str]:
        process = await asyncio.create_subprocess_exec(
            "bash",
            "-c",
            command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
            limit=1024 * 1024,
        )
        assert process.stdout is not None
        try:
            while True:
                try:
                    raw = await process.stdout.readline()
                except ValueError:
                    # A line longer than the buffer limit; skip it.
                    continue
                if not raw:
                    break
                yield clean_line(raw.decode(errors="replace"))
        finally:
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
            await process.wait()

    async def listdir(self, path: str) -> DirListing:
        target = Path(path or "~").expanduser()
        try:
            resolved = target.resolve(strict=True)
            entries = []
            for child in resolved.iterdir():
                try:
                    is_dir = child.is_dir()
                    size = None if is_dir else child.stat().st_size
                except OSError:
                    continue
                entries.append(DirEntry(name=child.name, is_dir=is_dir, size=size))
        except OSError as exc:
            raise FileNotFoundError(str(exc)) from exc
        parent = str(resolved.parent) if resolved.parent != resolved else None
        return DirListing(path=str(resolved), parent=parent, entries=sort_entries(entries))

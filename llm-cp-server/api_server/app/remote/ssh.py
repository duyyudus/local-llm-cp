from __future__ import annotations

import asyncio
import logging
import posixpath
import stat
import time
from collections.abc import AsyncIterator
from pathlib import Path

import asyncssh

from api_server.app.remote.executor import (
    CommandResult,
    ConnectionState,
    DirEntry,
    DirListing,
    RemoteUnavailableError,
    clean_line,
    sort_entries,
)
from common.config import Settings

logger = logging.getLogger(__name__)

RECONNECT_MIN_INTERVAL_SECONDS = 3.0


class SSHExecutor:
    """One persistent SSH connection to the GPU host, re-established on demand."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._conn: asyncssh.SSHClientConnection | None = None
        self._lock = asyncio.Lock()
        self._last_attempt = 0.0
        self._error: str | None = None

    @property
    def target(self) -> str:
        settings = self._settings
        user = f"{settings.gpu_ssh_user}@" if settings.gpu_ssh_user else ""
        return f"{user}{settings.gpu_ssh_host}:{settings.gpu_ssh_port}"

    @property
    def state(self) -> ConnectionState:
        return ConnectionState(
            mode="ssh",
            target=self.target,
            connected=self._conn is not None,
            error=self._error,
        )

    async def close(self) -> None:
        conn, self._conn = self._conn, None
        if conn is not None:
            conn.close()
            await conn.wait_closed()

    async def _connection(self) -> asyncssh.SSHClientConnection:
        if self._conn is not None:
            return self._conn
        async with self._lock:
            if self._conn is not None:
                return self._conn
            settings = self._settings
            if not settings.gpu_ssh_host:
                self._error = "GPU_SSH_HOST is not configured"
                raise RemoteUnavailableError(self._error)
            # Callers poll every few seconds; do not hammer an unreachable host.
            if time.monotonic() - self._last_attempt < RECONNECT_MIN_INTERVAL_SECONDS:
                raise RemoteUnavailableError(self._error or "SSH connection is not ready")
            self._last_attempt = time.monotonic()
            options: dict[str, object] = {
                "port": settings.gpu_ssh_port,
                "known_hosts": settings.gpu_ssh_known_hosts or None,
                "keepalive_interval": 15,
                "keepalive_count_max": 3,
                "connect_timeout": 10,
            }
            if settings.gpu_ssh_user:
                options["username"] = settings.gpu_ssh_user
            key_path = Path(settings.gpu_ssh_key_path).expanduser()
            # Docker mounts /dev/null here when no key is configured; only a real file counts.
            has_key = bool(settings.gpu_ssh_key_path) and key_path.is_file()
            if has_key:
                options["client_keys"] = [str(key_path)]
            if settings.gpu_ssh_password:
                options["password"] = settings.gpu_ssh_password
                if not has_key:
                    # Go straight to the password instead of offering default keys first.
                    options["client_keys"] = None
                    options["agent_path"] = None
            try:
                self._conn = await asyncssh.connect(settings.gpu_ssh_host, **options)
            except (OSError, asyncssh.Error, TimeoutError) as exc:
                self._error = f"SSH connection to {self.target} failed: {exc}"
                logger.warning(self._error)
                raise RemoteUnavailableError(self._error) from exc
            self._error = None
            logger.info("Connected to %s", self.target)
            return self._conn

    def _drop(self, conn: asyncssh.SSHClientConnection, exc: BaseException) -> None:
        if self._conn is conn:
            self._conn = None
            self._error = f"SSH connection to {self.target} lost: {exc}"
            logger.warning(self._error)
            conn.close()

    async def run(
        self, command: str, timeout: float = 15.0, input: str | None = None
    ) -> CommandResult:
        conn = await self._connection()
        try:
            result = await conn.run(
                command, check=False, timeout=timeout, errors="replace", input=input
            )
        except asyncssh.TimeoutError as exc:
            raise RemoteUnavailableError(f"Command timed out after {timeout:.0f}s") from exc
        except (OSError, asyncssh.Error) as exc:
            self._drop(conn, exc)
            raise RemoteUnavailableError(str(exc)) from exc
        return CommandResult(
            exit_status=result.exit_status if result.exit_status is not None else -1,
            stdout=str(result.stdout or ""),
            stderr=str(result.stderr or ""),
        )

    async def stream(self, command: str) -> AsyncIterator[str]:
        conn = await self._connection()
        try:
            # A pty makes sshd hang up the remote command when the channel or the
            # connection goes away, so `tail -F` and `nvidia-smi -l` never leak.
            process = await conn.create_process(command, term_type="dumb", errors="replace")
        except (OSError, asyncssh.Error) as exc:
            self._drop(conn, exc)
            raise RemoteUnavailableError(str(exc)) from exc
        try:
            async for raw in process.stdout:
                text = str(raw)
                # A fragment without a newline is what was in flight when the channel
                # closed; callers count lines to resume, so it must not be yielded.
                if text.endswith("\n"):
                    yield clean_line(text)
        except (OSError, asyncssh.Error) as exc:
            self._drop(conn, exc)
            raise RemoteUnavailableError(str(exc)) from exc
        finally:
            process.close()

    async def listdir(self, path: str) -> DirListing:
        conn = await self._connection()
        try:
            async with conn.start_sftp_client() as sftp:
                requested = path or "."
                if requested == "~" or requested.startswith("~/"):
                    requested = "." + requested[1:]
                resolved = await sftp.realpath(requested)
                entries = []
                for item in await sftp.readdir(resolved):
                    name = str(item.filename)
                    if name in (".", ".."):
                        continue
                    mode = item.attrs.permissions or 0
                    is_dir = stat.S_ISDIR(mode)
                    if stat.S_ISLNK(mode):
                        is_dir = await sftp.isdir(posixpath.join(str(resolved), name))
                    entries.append(
                        DirEntry(name=name, is_dir=is_dir, size=None if is_dir else item.attrs.size)
                    )
        except asyncssh.SFTPError as exc:
            raise FileNotFoundError(exc.reason) from exc
        except (OSError, asyncssh.Error) as exc:
            self._drop(conn, exc)
            raise RemoteUnavailableError(str(exc)) from exc
        resolved_path = str(resolved)
        parent = posixpath.dirname(resolved_path) if resolved_path != "/" else None
        return DirListing(path=resolved_path, parent=parent, entries=sort_entries(entries))

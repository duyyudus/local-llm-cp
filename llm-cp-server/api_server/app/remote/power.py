from __future__ import annotations

import contextlib

from api_server.app.remote.executor import RemoteExecutor, RemoteUnavailableError


class ShutdownError(Exception):
    pass


async def shutdown(executor: RemoteExecutor, command: str, password: str = "") -> None:
    """Power off the GPU host with the configured command."""
    # Fail here when the host is unreachable, so a dropped connection below can only
    # mean the host went down before the command returned.
    await executor.run("true")
    result = None
    with contextlib.suppress(RemoteUnavailableError):
        # `sudo -S` reads the password from stdin, so it never appears in the command
        # line. The newline also ends the read when no password is configured.
        result = await executor.run(command, input=f"{password}\n")
    if result is not None and not result.ok:
        detail = "; ".join(line.strip() for line in result.stderr.splitlines() if line.strip())
        detail = detail or f"exit status {result.exit_status}"
        raise ShutdownError(f"Shutdown command failed: {detail}")

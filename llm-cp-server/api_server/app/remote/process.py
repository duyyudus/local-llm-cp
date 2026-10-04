from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

from api_server.app.remote.engines import quote_path
from api_server.app.remote.executor import RemoteExecutor, bash
from common.config import Settings

LOG_FILE_NAME = "server.log"
KEPT_LOG_FILES = 5
PROFILE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class LaunchError(Exception):
    pass


@dataclass(frozen=True)
class Launch:
    pid: int
    log_path: str


@dataclass(frozen=True)
class Probe:
    pid: int
    http_code: str
    cmdline: str


def process_matches(command: list[str], cmdline: str) -> bool:
    """Guard against PID reuse: the live process must still be the one we launched."""
    return bool(command) and command[0] in cmdline


class ProcessManager:
    """Launches, inspects and stops detached server processes on the GPU host."""

    def __init__(self, executor: RemoteExecutor, settings: Settings) -> None:
        self._executor = executor
        self._settings = settings
        self._state_dir: str | None = None

    async def state_dir(self) -> str:
        if self._state_dir is None:
            configured = self._settings.remote_state_dir
            if configured == "~" or configured.startswith("~/"):
                result = await self._executor.run(bash('printf %s "$HOME"'))
                configured = result.stdout.strip() + configured[1:]
            self._state_dir = configured
        return self._state_dir

    async def executable_exists(self, executable: str) -> bool:
        result = await self._executor.run(
            bash(f"command -v -- {shlex.quote(executable)} >/dev/null 2>&1")
        )
        return result.ok

    async def launch(
        self, profile_id: str, argv: list[str], env: dict[str, str], cwd: str | None = None
    ) -> Launch:
        run_dir = f"{await self.state_dir()}/{profile_id}"
        log_path = f"{run_dir}/{LOG_FILE_NAME}"
        change_dir = f"cd -- {quote_path(cwd)}" if cwd else ""
        assignments = " ".join(shlex.quote(f"{key}={value}") for key, value in env.items())
        script = f"""
set -e
dir={shlex.quote(run_dir)}
log={shlex.quote(log_path)}
mkdir -p "$dir"
if [ -s "$log" ]; then
  i={KEPT_LOG_FILES - 1}
  while [ "$i" -ge 1 ]; do
    if [ -f "$log.$i" ]; then mv -f "$log.$i" "$log.$((i + 1))"; fi
    i=$((i - 1))
  done
  mv -f "$log" "$log.1"
fi
: > "$log"
{change_dir}
setsid nohup env {assignments} {shlex.join(argv)} >> "$log" 2>&1 < /dev/null &
echo $!
"""
        result = await self._executor.run(bash(script), timeout=30)
        pid_text = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
        if not result.ok or not pid_text.isdigit():
            detail = result.stderr.strip() or result.stdout.strip() or "no pid returned"
            raise LaunchError(f"Failed to launch process: {detail}")
        return Launch(pid=int(pid_text), log_path=log_path)

    async def remove_logs(self, profile_id: str) -> None:
        """Delete the profile's log folder on the GPU host."""
        # The id becomes part of an `rm -rf` path, so it must be a plain name.
        if not PROFILE_ID.match(profile_id):
            raise ValueError(f"Refusing to remove logs for unexpected profile id: {profile_id!r}")
        run_dir = f"{await self.state_dir()}/{profile_id}"
        await self._executor.run(bash(f"rm -rf -- {shlex.quote(run_dir)}"))

    async def probe(self, targets: list[tuple[int, str]]) -> dict[int, Probe]:
        """Return a Probe for every pid that is still alive, with its /health status code."""
        if not targets:
            return {}
        checks = []
        for pid, health_url in targets:
            checks.append(
                f"p={int(pid)}; "
                "if kill -0 $p 2>/dev/null; then "
                "c=$(tr '\\0' ' ' < /proc/$p/cmdline 2>/dev/null); "
                'if [ "$have_curl" = 1 ]; then '
                "h=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "
                f"{shlex.quote(health_url)} 2>/dev/null); "
                "else h=na; fi; "
                'printf \'%s\\t%s\\t%s\\n\' "$p" "${h:-000}" "$c"; fi'
            )
        script = (
            "have_curl=0; command -v curl >/dev/null 2>&1 && have_curl=1\n" + "\n".join(checks)
        )
        result = await self._executor.run(bash(script), timeout=10 + 3 * len(targets))
        probes: dict[int, Probe] = {}
        for line in result.stdout.splitlines():
            parts = line.split("\t", 2)
            if len(parts) == 3 and parts[0].isdigit():
                probes[int(parts[0])] = Probe(
                    pid=int(parts[0]), http_code=parts[1], cmdline=parts[2].strip()
                )
        return probes

    async def stop(self, pid: int) -> bool:
        """SIGTERM the process group, escalate to SIGKILL after the timeout."""
        timeout = self._settings.stop_timeout_seconds
        script = f"""
p={int(pid)}
kill -TERM -- -$p 2>/dev/null || kill -TERM $p 2>/dev/null
i=0
while [ "$i" -lt {timeout * 5} ]; do
  kill -0 $p 2>/dev/null || exit 0
  sleep 0.2
  i=$((i + 1))
done
kill -KILL -- -$p 2>/dev/null || kill -KILL $p 2>/dev/null
sleep 0.5
kill -0 $p 2>/dev/null && exit 1
exit 0
"""
        result = await self._executor.run(bash(script), timeout=timeout + 15)
        return result.ok

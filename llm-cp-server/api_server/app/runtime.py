from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api_server.app.remote.executor import RemoteExecutor, RemoteUnavailableError
from api_server.app.remote.gpu import GpuSampler
from api_server.app.remote.local import LocalExecutor
from api_server.app.remote.logs import LogHub
from api_server.app.remote.process import ProcessManager, process_matches
from api_server.app.remote.ssh import SSHExecutor
from common.config import Settings
from common.db.models import Profile, Run, utcnow

logger = logging.getLogger(__name__)

LOG_DRAIN_SECONDS = 2.0


@dataclass
class LiveRun:
    run_id: str
    profile_id: str
    profile_name: str
    pid: int
    status: str


def make_executor(settings: Settings) -> RemoteExecutor:
    if settings.remote_mode == "local":
        return LocalExecutor()
    return SSHExecutor(settings)


def status_from_http_code(code: str) -> str:
    if code == "200":
        return "ready"
    if code == "na":
        # curl is missing on the host, so readiness cannot be observed.
        return "running"
    return "starting"


class Runtime:
    """Process-wide state: the host connection, live run statuses, log and GPU streams."""

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        executor: RemoteExecutor | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.executor = executor or make_executor(settings)
        self.processes = ProcessManager(self.executor, settings)
        self.logs = LogHub(
            self.executor,
            max_lines=settings.log_buffer_lines,
            backlog_lines=settings.log_backlog_lines,
        )
        self.gpu = GpuSampler(
            self.executor,
            history_samples=settings.gpu_history_samples,
            process_interval=settings.gpu_process_interval_seconds,
            resolve_pid=self.profile_for_pid,
        )
        # Serialises start/stop with the status poll so they never race on a run.
        self.lock = asyncio.Lock()
        self.live: dict[str, LiveRun] = {}
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self.gpu.start()
        self._task = asyncio.create_task(self._poll())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self.gpu.close()
        await self.logs.close()
        await self.executor.close()

    def profile_for_pid(self, pid: int) -> tuple[str, str] | None:
        for run in self.live.values():
            if run.pid == pid:
                return run.profile_id, run.profile_name
        return None

    def status_for(self, profile_id: str) -> str | None:
        run = self.live.get(profile_id)
        return run.status if run else None

    async def _poll(self) -> None:
        while True:
            try:
                await self.refresh()
            except Exception:
                logger.exception("Run status refresh failed")
            await asyncio.sleep(self.settings.status_poll_interval_seconds)

    async def refresh(self) -> None:
        async with self.lock:
            await self.refresh_locked()

    async def refresh_locked(self) -> None:
        """Reconcile open runs in the database with what is alive on the GPU host."""
        async with self.session_factory() as session:
            rows = (
                await session.execute(
                    select(Run, Profile)
                    .join(Profile, Profile.id == Run.profile_id)
                    .where(Run.stopped_at.is_(None))
                )
            ).all()
            if not rows:
                self.live = {}
                return
            try:
                probes = await self.processes.probe([(run.pid, run.health_url) for run, _ in rows])
            except RemoteUnavailableError:
                self.live = {
                    profile.id: LiveRun(run.id, profile.id, profile.name, run.pid, "unknown")
                    for run, profile in rows
                }
                return
            live: dict[str, LiveRun] = {}
            for run, profile in rows:
                probe = probes.get(run.pid)
                if probe is None or not process_matches(run.command, probe.cmdline):
                    run.stopped_at = utcnow()
                    run.exit_reason = "exited"
                    self.logs.stop_tail(profile.id, delay=LOG_DRAIN_SECONDS)
                    logger.info("Profile %s (pid %s) exited", profile.name, run.pid)
                    continue
                status = status_from_http_code(probe.http_code)
                live[profile.id] = LiveRun(run.id, profile.id, profile.name, run.pid, status)
                self.logs.ensure_tail(profile.id, run.log_path)
            self.live = live
            await session.commit()

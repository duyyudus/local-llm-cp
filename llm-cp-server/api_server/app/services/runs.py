from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api_server.app.remote.engines import get_engine
from api_server.app.remote.process import LaunchError, process_matches
from api_server.app.runtime import LOG_DRAIN_SECONDS, LiveRun, Runtime
from common.db.models import Profile, Run, utcnow


async def start_profile(session: AsyncSession, runtime: Runtime, profile: Profile) -> None:
    engine = get_engine(profile.engine)
    async with runtime.lock:
        # Close runs whose process already died so they do not block this start.
        await runtime.refresh_locked()
        open_runs = (
            await session.execute(
                select(Run, Profile)
                .join(Profile, Profile.id == Run.profile_id)
                .where(Run.stopped_at.is_(None))
            )
        ).all()
        for run, other in open_runs:
            if run.profile_id == profile.id:
                raise HTTPException(status_code=409, detail="Profile is already running")
            if run.port == profile.port:
                raise HTTPException(
                    status_code=409,
                    detail=f"Port {profile.port} is in use by running profile '{other.name}'",
                )

        argv = engine.build_argv(profile)
        if not await runtime.processes.executable_exists(argv[0]):
            raise HTTPException(
                status_code=400,
                detail=f"Executable not found or not executable on the GPU host: {argv[0]}",
            )
        try:
            launch = await runtime.processes.launch(
                profile.id, argv, profile.env, engine.working_dir(profile)
            )
        except LaunchError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        await session.execute(delete(Run).where(Run.profile_id == profile.id))
        run = Run(
            profile_id=profile.id,
            pid=launch.pid,
            command=argv,
            port=profile.port,
            health_url=engine.health_url(profile),
            log_path=launch.log_path,
        )
        session.add(run)
        # Commit before releasing the lock so the status poll sees the new run.
        await session.commit()
        runtime.live[profile.id] = LiveRun(run.id, profile.id, profile.name, run.pid, "starting")
        runtime.logs.start_tail(profile.id, launch.log_path, fresh=True)


async def stop_profile(session: AsyncSession, runtime: Runtime, profile: Profile) -> None:
    async with runtime.lock:
        run = await session.scalar(
            select(Run).where(Run.profile_id == profile.id, Run.stopped_at.is_(None))
        )
        if run is None:
            raise HTTPException(status_code=409, detail="Profile is not running")
        probes = await runtime.processes.probe([(run.pid, run.health_url)])
        probe = probes.get(run.pid)
        if (
            probe is not None
            and process_matches(run.command, probe.cmdline)
            and not await runtime.processes.stop(run.pid)
        ):
            raise HTTPException(status_code=502, detail=f"Process {run.pid} could not be stopped")
        run.stopped_at = utcnow()
        run.exit_reason = "stopped"
        await session.commit()
        runtime.live.pop(profile.id, None)
        runtime.logs.stop_tail(profile.id, delay=LOG_DRAIN_SECONDS)

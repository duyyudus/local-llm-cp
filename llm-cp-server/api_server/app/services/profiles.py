from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_server.app.remote.engines import command_line, get_engine
from api_server.app.remote.executor import RemoteUnavailableError
from api_server.app.runtime import Runtime
from api_server.app.schemas import ProfileCreate, ProfileRead, ProfileUpdate, RunStatus
from common.db.models import Profile, Run

logger = logging.getLogger(__name__)

COPIED_FIELDS = (
    "engine",
    "executable_path",
    "working_dir",
    "model_path",
    "alias",
    "host",
    "port",
    "ctx_size",
    "n_gpu_layers",
    "notes",
)


def build_argv(profile) -> list[str]:
    return get_engine(profile.engine).build_argv(profile)


def preview_command(profile) -> str:
    engine = get_engine(profile.engine)
    return command_line(engine.build_argv(profile), profile.env, engine.working_dir(profile))


async def latest_runs(session: AsyncSession, profile_ids: list[str]) -> dict[str, Run]:
    if not profile_ids:
        return {}
    rows = await session.scalars(
        select(Run).where(Run.profile_id.in_(profile_ids)).order_by(Run.started_at)
    )
    return {run.profile_id: run for run in rows}


def run_status(profile: Profile, run: Run | None, runtime: Runtime, argv: list[str]) -> RunStatus:
    if run is None:
        return RunStatus()
    if run.stopped_at is None:
        return RunStatus(
            status=runtime.status_for(profile.id) or "unknown",
            pid=run.pid,
            started_at=run.started_at,
            command_changed=run.command != argv,
        )
    return RunStatus(
        status="exited" if run.exit_reason == "exited" else "stopped",
        started_at=run.started_at,
        stopped_at=run.stopped_at,
    )


def to_read(profile: Profile, run: Run | None, runtime: Runtime) -> ProfileRead:
    argv = build_argv(profile)
    return ProfileRead.model_validate(
        {
            **{column.name: getattr(profile, column.name) for column in Profile.__table__.columns},
            "command": preview_command(profile),
            "run": run_status(profile, run, runtime, argv),
        }
    )


async def read_profile(session: AsyncSession, runtime: Runtime, profile: Profile) -> ProfileRead:
    runs = await latest_runs(session, [profile.id])
    return to_read(profile, runs.get(profile.id), runtime)


async def list_profiles(session: AsyncSession, runtime: Runtime) -> list[ProfileRead]:
    profiles = list(await session.scalars(select(Profile).order_by(Profile.name)))
    runs = await latest_runs(session, [profile.id for profile in profiles])
    return [to_read(profile, runs.get(profile.id), runtime) for profile in profiles]


async def get_profile(session: AsyncSession, profile_id: str) -> Profile:
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


async def _ensure_name_free(session: AsyncSession, name: str, exclude_id: str | None) -> None:
    existing = await session.scalar(select(Profile).where(Profile.name == name))
    if existing is not None and existing.id != exclude_id:
        raise HTTPException(status_code=409, detail=f"A profile named '{name}' already exists")


async def create_profile(session: AsyncSession, payload: ProfileCreate) -> Profile:
    await _ensure_name_free(session, payload.name, None)
    profile = Profile(**payload.model_dump())
    session.add(profile)
    await session.flush()
    return profile


async def update_profile(
    session: AsyncSession, profile: Profile, payload: ProfileUpdate
) -> Profile:
    changes = payload.model_dump(exclude_unset=True)
    # Only optional fields may be cleared; a null for any other field means "leave unchanged".
    nullable = {"working_dir", "model_path", "alias", "ctx_size", "n_gpu_layers"}
    changes = {key: value for key, value in changes.items() if value is not None or key in nullable}
    if "name" in changes:
        await _ensure_name_free(session, changes["name"], profile.id)
    for key, value in changes.items():
        setattr(profile, key, value)
    await session.flush()
    return profile


async def duplicate_profile(session: AsyncSession, profile: Profile) -> Profile:
    names = set(await session.scalars(select(Profile.name)))
    name = f"{profile.name} (copy)"
    counter = 2
    while name in names:
        name = f"{profile.name} (copy {counter})"
        counter += 1
    clone = Profile(
        name=name,
        extra_args=list(profile.extra_args),
        env=dict(profile.env),
        **{field: getattr(profile, field) for field in COPIED_FIELDS},
    )
    session.add(clone)
    await session.flush()
    return clone


async def delete_profile(session: AsyncSession, runtime: Runtime, profile: Profile) -> None:
    open_run = await session.scalar(
        select(Run).where(Run.profile_id == profile.id, Run.stopped_at.is_(None))
    )
    if open_run is not None:
        raise HTTPException(status_code=409, detail="Stop the profile before deleting it")
    await session.delete(profile)
    runtime.logs.forget(profile.id)
    try:
        await runtime.processes.remove_logs(profile.id)
    except RemoteUnavailableError:
        # The profile is still deleted; its logs stay on the host until removed by hand.
        logger.warning("GPU host unavailable, logs of profile %s were not removed", profile.name)

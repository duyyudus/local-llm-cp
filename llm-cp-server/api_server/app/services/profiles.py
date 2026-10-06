from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api_server.app.remote.engines import command_line, get_engine
from api_server.app.remote.executor import RemoteUnavailableError
from api_server.app.runtime import Runtime
from api_server.app.schemas import (
    ImportConflict,
    ImportResult,
    ProfileCreate,
    ProfileExport,
    ProfileRead,
    ProfileUpdate,
    RunStatus,
)
from api_server.app.schemas.profiles import EXPORT_FORMAT, EXPORT_VERSION
from common.db.models import Profile, Run, utcnow

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


DISPLAY_ORDER = (Profile.position, Profile.name)


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
    profiles = list(await session.scalars(select(Profile).order_by(*DISPLAY_ORDER)))
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


async def _next_position(session: AsyncSession) -> int:
    last = await session.scalar(select(func.max(Profile.position)))
    return 0 if last is None else last + 1


async def create_profile(session: AsyncSession, payload: ProfileCreate) -> Profile:
    await _ensure_name_free(session, payload.name, None)
    profile = Profile(**payload.model_dump(), position=await _next_position(session))
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
    # A partial update can only be checked against the engine once it is applied.
    try:
        get_engine(profile.engine).validate(profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.flush()
    return profile


def _unused_name(name: str, label: str, names: set[str]) -> str:
    candidate = f"{name} ({label})"
    counter = 2
    while candidate in names:
        candidate = f"{name} ({label} {counter})"
        counter += 1
    return candidate


async def duplicate_profile(session: AsyncSession, profile: Profile) -> Profile:
    names = set(await session.scalars(select(Profile.name)))
    clone = Profile(
        name=_unused_name(profile.name, "copy", names),
        engine_options=dict(profile.engine_options),
        extra_args=list(profile.extra_args),
        env=dict(profile.env),
        position=await _next_position(session),
        **{field: getattr(profile, field) for field in COPIED_FIELDS},
    )
    session.add(clone)
    await session.flush()
    return clone


async def reorder_profiles(session: AsyncSession, profile_ids: list[str]) -> None:
    profiles = list(await session.scalars(select(Profile).order_by(*DISPLAY_ORDER)))
    by_id = {profile.id: profile for profile in profiles}
    # Ids the caller did not know about, or no longer exist, must not fail the whole move.
    listed = [profile_id for profile_id in dict.fromkeys(profile_ids) if profile_id in by_id]
    ordered = [by_id[profile_id] for profile_id in listed]
    ordered += [profile for profile in profiles if profile.id not in listed]
    for position, profile in enumerate(ordered):
        profile.position = position
    await session.flush()


async def export_profiles(session: AsyncSession, profile_ids: list[str] | None) -> ProfileExport:
    query = select(Profile).order_by(*DISPLAY_ORDER)
    if profile_ids:
        query = query.where(Profile.id.in_(profile_ids))
    profiles = list(await session.scalars(query))
    missing = set(profile_ids or ()) - {profile.id for profile in profiles}
    if missing:
        raise HTTPException(status_code=404, detail=f"Profile not found: {sorted(missing)[0]}")
    return ProfileExport(
        format=EXPORT_FORMAT,
        version=EXPORT_VERSION,
        exported_at=utcnow(),
        profiles=[ProfileCreate.model_validate(item, from_attributes=True) for item in profiles],
    )


async def import_profiles(
    session: AsyncSession, document: ProfileExport, on_conflict: ImportConflict
) -> ImportResult:
    existing = {profile.name: profile for profile in await session.scalars(select(Profile))}
    result = ImportResult(created=[], updated=[], skipped=[])
    position = await _next_position(session)
    for payload in document.profiles:
        values = payload.model_dump()
        current = existing.get(payload.name)
        if current is not None and on_conflict == "skip":
            result.skipped.append(payload.name)
            continue
        if current is not None and on_conflict == "overwrite":
            for key, value in values.items():
                setattr(current, key, value)
            result.updated.append(payload.name)
            continue
        if current is not None:
            values["name"] = _unused_name(payload.name, "imported", set(existing))
        profile = Profile(**values, position=position)
        position += 1
        session.add(profile)
        existing[profile.name] = profile
        result.created.append(profile.name)
    await session.flush()
    return result


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

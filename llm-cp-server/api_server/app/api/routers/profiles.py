from __future__ import annotations

from fastapi import APIRouter, status

from api_server.app.api.dependencies import RuntimeDep, SessionDep
from api_server.app.schemas import (
    CommandPreview,
    ListEnvelope,
    ProfileCreate,
    ProfileRead,
    ProfileUpdate,
)
from api_server.app.services import profiles as profile_service

router = APIRouter()


@router.get("/profiles", response_model=ListEnvelope[ProfileRead])
async def list_profiles(session: SessionDep, runtime: RuntimeDep) -> ListEnvelope[ProfileRead]:
    items = await profile_service.list_profiles(session, runtime)
    return ListEnvelope(items=items, total=len(items))


@router.post("/profiles", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(
    payload: ProfileCreate, session: SessionDep, runtime: RuntimeDep
) -> ProfileRead:
    profile = await profile_service.create_profile(session, payload)
    return await profile_service.read_profile(session, runtime, profile)


@router.post("/profiles/preview-command", response_model=CommandPreview)
async def preview_command(payload: ProfileCreate) -> CommandPreview:
    argv = profile_service.build_argv(payload)
    return CommandPreview(command=profile_service.preview_command(payload), argv=argv)


@router.get("/profiles/{profile_id}", response_model=ProfileRead)
async def get_profile(profile_id: str, session: SessionDep, runtime: RuntimeDep) -> ProfileRead:
    profile = await profile_service.get_profile(session, profile_id)
    return await profile_service.read_profile(session, runtime, profile)


@router.patch("/profiles/{profile_id}", response_model=ProfileRead)
async def update_profile(
    profile_id: str, payload: ProfileUpdate, session: SessionDep, runtime: RuntimeDep
) -> ProfileRead:
    profile = await profile_service.get_profile(session, profile_id)
    profile = await profile_service.update_profile(session, profile, payload)
    return await profile_service.read_profile(session, runtime, profile)


@router.post(
    "/profiles/{profile_id}/duplicate",
    response_model=ProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_profile(
    profile_id: str, session: SessionDep, runtime: RuntimeDep
) -> ProfileRead:
    profile = await profile_service.get_profile(session, profile_id)
    clone = await profile_service.duplicate_profile(session, profile)
    return await profile_service.read_profile(session, runtime, clone)


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile_id: str, session: SessionDep, runtime: RuntimeDep) -> None:
    profile = await profile_service.get_profile(session, profile_id)
    await profile_service.delete_profile(session, runtime, profile)

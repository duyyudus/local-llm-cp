from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api_server.app.db import get_session, get_settings
from api_server.app.runtime import Runtime
from common.config import Settings


def get_runtime(request: Request) -> Runtime:
    return request.app.state.runtime


def mark_active(request: Request) -> None:
    """Any dashboard request resumes host polling; health probes do not count."""
    request.app.state.runtime.activity.touch()


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
RuntimeDep = Annotated[Runtime, Depends(get_runtime)]

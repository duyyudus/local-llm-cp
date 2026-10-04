from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from api_server.app.api.dependencies import RuntimeDep, SessionDep, SettingsDep

router = APIRouter()


@router.get("/health")
async def health(settings: SettingsDep) -> dict[str, object]:
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@router.get("/ready", response_model=None)
async def ready(session: SessionDep, runtime: RuntimeDep):
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unavailable", "error": str(exc)},
        )
    # The GPU host being offline does not make the API itself unready.
    return {"status": "ready", "database": "ok", "host_connected": runtime.executor.state.connected}

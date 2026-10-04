from fastapi import APIRouter, Depends

from api_server.app.api.dependencies import mark_active
from api_server.app.api.routers import health, host, profiles, runs

router = APIRouter()
router.include_router(health.router)
for dashboard_router in (host.router, profiles.router, runs.router):
    router.include_router(dashboard_router, dependencies=[Depends(mark_active)])

__all__ = ["router"]

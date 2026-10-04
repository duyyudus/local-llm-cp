from fastapi import APIRouter

from api_server.app.api.routers import health, host, profiles, runs

router = APIRouter()
router.include_router(health.router)
router.include_router(host.router)
router.include_router(profiles.router)
router.include_router(runs.router)

__all__ = ["router"]

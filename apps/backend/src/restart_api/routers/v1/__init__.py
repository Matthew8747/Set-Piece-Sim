"""Versioned API surface. Domain routers (scenarios, sim-runs, optimizations)
mount here in later phases; Phase 0 ships only ``/meta`` so the version prefix,
DTO discipline, and OpenAPI wiring are exercised end to end."""

from fastapi import APIRouter, Depends

from restart import ENGINE_VERSION
from restart_api import __version__
from restart_api.routers.v1 import setpieces
from restart_api.schemas import MetaResponse
from restart_api.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1")
router.include_router(setpieces.router)


@router.get("/meta", response_model=MetaResponse, tags=["meta"])
def meta(settings: Settings = Depends(get_settings)) -> MetaResponse:  # noqa: B008
    return MetaResponse(
        api_version=__version__,
        engine_version=ENGINE_VERSION,
        environment=settings.app_env,
    )

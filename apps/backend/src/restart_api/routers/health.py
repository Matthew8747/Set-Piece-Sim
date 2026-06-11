"""Liveness/readiness endpoints (unversioned: they outlive API versions).

``/healthz`` deliberately reports the simulation core's ENGINE_VERSION - it
proves the cross-package workspace dependency is intact, and operationally it
answers "which physics is this deployment running?" at a glance.
"""

from fastapi import APIRouter

from restart import ENGINE_VERSION
from restart_api import __version__
from restart_api.schemas import HealthResponse, ReadyResponse

router = APIRouter(tags=["ops"])


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", api_version=__version__, engine_version=ENGINE_VERSION)


@router.get("/readyz", response_model=ReadyResponse)
def readyz() -> ReadyResponse:
    # No external dependencies exist yet; checks are explicit 'skipped' rather
    # than silently absent, so the contract shape is stable from day one.
    return ReadyResponse(status="ready", checks={"database": "skipped", "redis": "skipped"})

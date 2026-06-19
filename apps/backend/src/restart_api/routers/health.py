"""Liveness/readiness endpoints (unversioned: they outlive API versions).

``/healthz`` deliberately reports the simulation core's ENGINE_VERSION - it
proves the cross-package workspace dependency is intact, and operationally it
answers "which physics is this deployment running?" at a glance.

``/readyz`` probes whatever backends are *configured* (ADR-007 d1/d2): with the
file/in-process defaults there is nothing external, so checks are ``skipped``;
when a Postgres/Redis URL is set the probe really connects and the endpoint
fails (503) if the dependency is unreachable.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from restart import ENGINE_VERSION
from restart_api import __version__
from restart_api.schemas import HealthResponse, ReadyResponse
from restart_api.settings import Settings, get_settings

router = APIRouter(tags=["ops"])

Check = Literal["ok", "skipped"]


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", api_version=__version__, engine_version=ENGINE_VERSION)


def _probe_database(settings: Settings) -> Check:
    if settings.database_url is None:
        return "skipped"
    try:
        import psycopg

        with psycopg.connect(settings.database_url.get_secret_value(), connect_timeout=2) as conn:
            conn.execute("SELECT 1")
    except Exception as exc:  # surfaced as 503, not a 500 stack trace
        raise HTTPException(status_code=503, detail=f"database not ready: {exc}") from exc
    return "ok"


def _probe_redis(settings: Settings) -> Check:
    if settings.redis_url is None:
        return "skipped"
    try:
        from redis import Redis

        client = Redis.from_url(settings.redis_url.get_secret_value(), socket_connect_timeout=2)
        try:
            client.ping()
        finally:
            client.close()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"redis not ready: {exc}") from exc
    return "ok"


@router.get("/readyz", response_model=ReadyResponse)
def readyz(settings: Settings = Depends(get_settings)) -> ReadyResponse:  # noqa: B008
    checks: dict[str, Check] = {
        "database": _probe_database(settings),
        "redis": _probe_redis(settings),
    }
    return ReadyResponse(status="ready", checks=checks)

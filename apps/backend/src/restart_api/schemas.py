"""Response DTOs. Domain types never serialize directly to JSON; these models
are the explicit boundary contract (and the source of OpenAPI schemas)."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    api_version: str
    engine_version: str


class ReadyResponse(BaseModel):
    status: Literal["ready"]
    # Per-dependency readiness lands here when Postgres/Redis arrive (Phase 4/6).
    checks: dict[str, Literal["ok", "skipped"]]


class MetaResponse(BaseModel):
    api_version: str
    engine_version: str
    environment: str

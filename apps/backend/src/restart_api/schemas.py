"""Response DTOs. Domain types never serialize directly to JSON; these models
are the explicit boundary contract (and the source of OpenAPI schemas).

Keep field names/shapes in sync with packages/shared-types/src/index.ts
(hand-mirrored until OpenAPI codegen lands in Phase 6 — tech-debt register)."""

from typing import Literal

from pydantic import BaseModel, Field


class ProblemFieldError(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ProblemDetail(BaseModel):
    """RFC 9457 problem-details body — the API's single error contract."""

    type: str
    title: str
    status: int
    detail: str
    errors: list[ProblemFieldError] | None = None


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


# --- Set-piece MVP DTOs (Phase 3) -------------------------------------------


class RoutineSummary(BaseModel):
    routine_id: str
    name: str
    set_piece: str


class SchemeSummary(BaseModel):
    scheme_id: str
    name: str


class EventDTO(BaseModel):
    kind: str
    time_s: float
    player_id: str | None = None
    team: str | None = None
    # Real-data xG of a shot event (None for non-shots or before a model is wired).
    xg: float | None = None


class SimulateRequest(BaseModel):
    routine_id: str
    scheme_id: str
    seed: int = Field(default=0, ge=0, le=2**31 - 1)


class SimulateResponse(BaseModel):
    engine_version: str
    seed: int
    outcome: str
    events: list[EventDTO]
    track_times_s: list[float]
    att_tracks: list[list[list[float]]]  # (T, na, 2)
    def_tracks: list[list[list[float]]]  # (T, nd, 2)
    ball_path: list[list[float]]  # (samples, 3)


class ProportionCIDTO(BaseModel):
    p: float
    lo: float
    hi: float
    k: int
    n: int


class MonteCarloRequest(BaseModel):
    routine_id: str
    scheme_id: str
    # Hard upper bound = cost-bomb protection (security checklist doc 02 §9).
    n_sims: int = Field(default=200, ge=1, le=2000)
    root_seed: int = Field(default=0, ge=0, le=2**31 - 1)


class MonteCarloResponse(BaseModel):
    engine_version: str
    root_seed: int
    n_sims: int
    p_goal: ProportionCIDTO
    p_shot: ProportionCIDTO
    p_header_shot: ProportionCIDTO
    p_first_contact_attack: ProportionCIDTO
    p_clearance: ProportionCIDTO
    p_possession_recovered: ProportionCIDTO
    outcome_counts: dict[str, int]
    # Mean real-data xG per simulation, the count of scored shots, and which
    # model produced it (None when no xG model is active).
    mean_xg: float
    n_xg_scored: int
    xg_model: str | None = None

"""Response DTOs. Domain types never serialize directly to JSON; these models
are the explicit boundary contract (and the source of OpenAPI schemas).

Keep field names/shapes in sync with packages/shared-types/src/index.ts
(hand-mirrored until OpenAPI codegen lands in Phase 6 — tech-debt register)."""

from typing import Literal

from pydantic import BaseModel, Field

# Pitch is the canonical 105 x 68 m surface (doc 07). Coordinates are treated as
# hostile input (sim inputs are effectively code — security checklist doc 02 9);
# this point is reused by every scenario DTO that carries a position.
PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0


class PitchPoint(BaseModel):
    x: float = Field(ge=0.0, le=PITCH_LENGTH_M)
    y: float = Field(ge=0.0, le=PITCH_WIDTH_M)


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


# Default error responses documented on every router, so OpenAPI (and the
# generated TS client) advertise the problem+json contract per status code.
ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    404: {
        "model": ProblemDetail,
        "content": {
            "application/problem+json": {"schema": {"$ref": "#/components/schemas/ProblemDetail"}}
        },
        "description": "Resource not found",
    },
    422: {
        "model": ProblemDetail,
        "content": {
            "application/problem+json": {"schema": {"$ref": "#/components/schemas/ProblemDetail"}}
        },
        "description": "Request validation failed",
    },
    429: {
        "model": ProblemDetail,
        "content": {
            "application/problem+json": {"schema": {"$ref": "#/components/schemas/ProblemDetail"}}
        },
        "description": "Rate limit exceeded",
    },
}


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

# Canonical matchup defaults so Phase-3 callers (no team ids) keep working while
# the demo squads are retired; real squads come from the marts (ADR-007 d2).
DEFAULT_ATTACKING_TEAM = "england"
DEFAULT_DEFENDING_TEAM = "argentina"


class RoutineSummary(BaseModel):
    routine_id: str
    name: str
    set_piece: str


class SchemeSummary(BaseModel):
    scheme_id: str
    name: str


class TeamSummaryDTO(BaseModel):
    team_id: str
    name: str
    country: str
    n_players: int


class PlayerDTO(BaseModel):
    player_id: str
    display_name: str
    position_group: str
    heading: float
    delivery: float
    jump_reach_m: float
    height_m: float
    # Provenance: every attribute is derived from open data, never scraped.
    source: str


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
    attacking_team_id: str = DEFAULT_ATTACKING_TEAM
    defending_team_id: str = DEFAULT_DEFENDING_TEAM
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
    attacking_team_id: str = DEFAULT_ATTACKING_TEAM
    defending_team_id: str = DEFAULT_DEFENDING_TEAM
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

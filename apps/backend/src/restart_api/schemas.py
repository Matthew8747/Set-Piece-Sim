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


# --- Read-only optimization surface (Phase 7) ------------------------------
# Typed view over the persisted study.json artifact. restart_opt is never
# imported in the request path: these DTOs carry derived, pre-computed data so
# the OpenAPI/shared-types drift gate covers the whole contract (ADR-008).


class MatchupDTO(BaseModel):
    attacking: str
    defending: str
    scheme: str


class ConvergencePointDTO(BaseModel):
    trial: int  # 1-based trial index
    best_so_far: float  # cumulative-max mean xG through this trial


class AxisDTO(BaseModel):
    """One parallel-coordinates axis. Continuous axes carry a numeric domain;
    categorical axes carry their category order so the client can ladder them."""

    name: str
    kind: Literal["continuous", "categorical"]
    domain: list[float] | None = None  # [min, max] for continuous
    categories: list[str] | None = None  # order for categorical
    importance: float  # SHAP importance (0.0 when the surrogate omits it)


class TrialDTO(BaseModel):
    params: dict[str, float | str]
    value: float
    state: str


class ConfirmRowDTO(BaseModel):
    params: dict[str, float | str]
    mean_xg: float
    ci_lo: float
    ci_hi: float
    n_sims: int


class WinnerDTO(BaseModel):
    mean_xg: float
    ci: list[float]
    beats_baseline: bool
    boundary_flags: list[str]
    face_validity_flags: list[str]


class SensitivityDTO(BaseModel):
    verdict: str
    top1_stable: bool
    rankings_flip: bool
    flipped: list[str]


class OptimizationSummaryDTO(BaseModel):
    id: str
    name: str
    matchup: MatchupDTO
    engine_version: str
    created_at: str
    winner_mean_xg: float
    winner_ci: list[float]
    beats_baseline: bool
    n_trials: int
    stale: bool  # study engine_version != current ENGINE_VERSION


class OptimizationDetailDTO(BaseModel):
    id: str
    name: str
    matchup: MatchupDTO
    engine_version: str
    created_at: str
    stale: bool
    convergence_tpe: list[ConvergencePointDTO]
    convergence_random: list[ConvergencePointDTO]
    baseline_mean_xg: float
    baseline_ci: list[float]
    trials: list[TrialDTO]
    axes: list[AxisDTO]
    confirm: list[ConfirmRowDTO]
    feature_importance: dict[str, float]
    insights: list[str]
    sensitivity: SensitivityDTO
    winner: WinnerDTO


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


# --- Scenario persistence + async sim-runs (Phase 6) ------------------------


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    routine_id: str
    scheme_id: str
    attacking_team_id: str = DEFAULT_ATTACKING_TEAM
    defending_team_id: str = DEFAULT_DEFENDING_TEAM


class ScenarioDTO(BaseModel):
    scenario_id: str
    name: str
    spec: dict[str, str]  # routine/scheme/team ids (string-valued)
    scenario_hash: str
    created_at: str


class SimRunCreate(BaseModel):
    scenario_id: str
    # Hard upper bound = cost-bomb protection (security checklist doc 02 §9).
    n_sims: int = Field(default=1000, ge=1, le=2000)
    root_seed: int = Field(default=0, ge=0, le=2**31 - 1)


class SimRunResultDTO(MonteCarloResponse):
    # Per-sim xG sample for the distribution charts + seeds the Replay picker
    # re-runs for the worst/median/best trajectories.
    xg_samples: list[float]
    replay_seeds: dict[str, int]


class SimRunStatusDTO(BaseModel):
    run_id: str
    scenario_id: str
    status: Literal["queued", "running", "complete", "failed"]
    progress: float
    n_sims: int
    root_seed: int
    engine_version: str
    created_at: str
    result: SimRunResultDTO | None = None
    error: dict[str, str] | None = None

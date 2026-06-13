"""Set-piece MVP endpoints: routine catalog, single simulation, Monte Carlo.

MVP scope (Phase 3 integration proof): the catalog is the simulation-core
content library against fixed demo teams; persistence, custom routines, and
async job execution arrive with Phase 4/6 per the roadmap. Sim counts are
hard-bounded (cost-bomb protection, security checklist doc 02 §9).
"""

from functools import lru_cache

from fastapi import APIRouter, HTTPException

from restart import ENGINE_VERSION
from restart.engine import SetPieceEngine, SetPieceResult
from restart.montecarlo import MonteCarloRunner, build_report
from restart.players.demo import demo_team
from restart.players.player import PositionGroup
from restart.tactics.compile import Scenario, SimProgram, compile_scenario
from restart.tactics.library import all_corner_routines, all_schemes
from restart_api.schemas import (
    EventDTO,
    MonteCarloRequest,
    MonteCarloResponse,
    RoutineSummary,
    SchemeSummary,
    SimulateRequest,
    SimulateResponse,
)

router = APIRouter(prefix="/setpieces", tags=["setpieces"])

_ATTACKING = demo_team("ENG", "England (demo)", 1)
_DEFENDING = demo_team("ARG", "Argentina (demo)", 2)
_ENGINE = SetPieceEngine()
_RUNNER = MonteCarloRunner(_ENGINE)


def _slug(name: str) -> str:
    return name.lower().replace(" ", "-")


_ROUTINES = {_slug(r.name): r for r in all_corner_routines()}
_SCHEMES = {_slug(s.name): s for s in all_schemes()}


@lru_cache(maxsize=64)
def _program(routine_id: str, scheme_id: str) -> SimProgram:
    routine = _ROUTINES.get(routine_id)
    scheme = _SCHEMES.get(scheme_id)
    if routine is None:
        raise HTTPException(status_code=404, detail=f"unknown routine_id {routine_id!r}")
    if scheme is None:
        raise HTTPException(status_code=404, detail=f"unknown scheme_id {scheme_id!r}")
    kicker = max(_ATTACKING.players, key=lambda p: p.attributes.delivery).player_id
    outfield = [
        p.player_id
        for p in _ATTACKING.players
        if p.position_group is not PositionGroup.GK and p.player_id != kicker
    ]
    roles = {a.role: outfield[i] for i, a in enumerate(routine.assignments)}
    return compile_scenario(
        Scenario(
            routine=routine,
            attacking_team=_ATTACKING,
            defending_team=_DEFENDING,
            kicker_id=kicker,
            role_assignments=roles,
            scheme=scheme,
        )
    )


def _to_response(result: SetPieceResult) -> SimulateResponse:
    events = [
        EventDTO(
            kind=e.kind,
            time_s=round(e.time_s, 3),
            player_id=getattr(e, "player_id", None),
            team=getattr(e, "team", None),
        )
        for e in result.events
    ]
    # Replay payloads decimated for transport (every 5th tick = 10 Hz).
    ball = result.delivery.samples.positions[::40].tolist()  # 5 ms steps -> 5 Hz
    return SimulateResponse(
        engine_version=ENGINE_VERSION,
        seed=result.seed,
        outcome=result.outcome.value,
        events=events,
        track_times_s=result.track_times_s[::5].tolist(),
        att_tracks=result.att_tracks[::5].tolist(),
        def_tracks=result.def_tracks[::5].tolist(),
        ball_path=ball,
    )


@router.get("/routines", response_model=list[RoutineSummary])
def list_routines() -> list[RoutineSummary]:
    return [
        RoutineSummary(routine_id=rid, name=r.name, set_piece=r.set_piece.value)
        for rid, r in _ROUTINES.items()
    ]


@router.get("/schemes", response_model=list[SchemeSummary])
def list_schemes() -> list[SchemeSummary]:
    return [SchemeSummary(scheme_id=sid, name=s.name) for sid, s in _SCHEMES.items()]


@router.post("/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest) -> SimulateResponse:
    program = _program(req.routine_id, req.scheme_id)
    return _to_response(_ENGINE.run(program, req.seed))


@router.post("/montecarlo", response_model=MonteCarloResponse)
def montecarlo(req: MonteCarloRequest) -> MonteCarloResponse:
    program = _program(req.routine_id, req.scheme_id)
    report = build_report(_RUNNER.run(program, req.n_sims, req.root_seed))
    return MonteCarloResponse(**report.to_dict())

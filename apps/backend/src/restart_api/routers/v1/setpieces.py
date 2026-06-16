"""Set-piece endpoints: routine catalog, single simulation, Monte Carlo.

The catalog is the simulation-core content library; squads are the real
mart-derived nations (demo squads retired from the runtime — ADR-007 d2). The
engine/runner/catalog and the program builder are shared with the async job
worker via ``restart_api.programs``. Sim counts are hard-bounded (cost-bomb
protection, security checklist doc 02 §9).
"""

from fastapi import APIRouter, Depends, Request

from restart import ENGINE_VERSION
from restart.engine import SetPieceResult
from restart.montecarlo import build_report
from restart_api import programs
from restart_api.ratelimit import limiter, write_limit
from restart_api.schemas import (
    EventDTO,
    MonteCarloRequest,
    MonteCarloResponse,
    RoutineSummary,
    SchemeSummary,
    SimulateRequest,
    SimulateResponse,
)
from restart_api.security import require_write_access

router = APIRouter(prefix="/setpieces", tags=["setpieces"])


def _to_response(result: SetPieceResult) -> SimulateResponse:
    events = [
        EventDTO(
            kind=e.kind,
            time_s=round(e.time_s, 3),
            player_id=getattr(e, "player_id", None),
            team=getattr(e, "team", None),
            xg=getattr(e, "xg", None),
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
        for rid, r in programs.ROUTINES.items()
    ]


@router.get("/schemes", response_model=list[SchemeSummary])
def list_schemes() -> list[SchemeSummary]:
    return [SchemeSummary(scheme_id=sid, name=s.name) for sid, s in programs.SCHEMES.items()]


@router.post(
    "/simulate", response_model=SimulateResponse, dependencies=[Depends(require_write_access)]
)
@limiter.limit(write_limit)
def simulate(request: Request, req: SimulateRequest) -> SimulateResponse:
    program = programs.build_program(
        req.routine_id, req.scheme_id, req.attacking_team_id, req.defending_team_id
    )
    return _to_response(programs.ENGINE.run(program, req.seed))


@router.post(
    "/montecarlo", response_model=MonteCarloResponse, dependencies=[Depends(require_write_access)]
)
@limiter.limit(write_limit)
def montecarlo(request: Request, req: MonteCarloRequest) -> MonteCarloResponse:
    program = programs.build_program(
        req.routine_id, req.scheme_id, req.attacking_team_id, req.defending_team_id
    )
    report = build_report(programs.RUNNER.run(program, req.n_sims, req.root_seed))
    return MonteCarloResponse(**report.to_dict(), xg_model=programs.XG_MODEL_ID)

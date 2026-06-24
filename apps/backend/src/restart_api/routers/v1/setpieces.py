"""Set-piece endpoints: routine catalog, single simulation, Monte Carlo.

The catalog is the simulation-core content library; squads are the real
mart-derived nations (demo squads retired from the runtime - ADR-007 d2). The
engine/runner/catalog and the program builder are shared with the async job
worker via ``restart_api.programs``. Sim counts are hard-bounded (cost-bomb
protection, security checklist doc 02 §9).
"""

from fastapi import APIRouter, Depends, Request

from restart.montecarlo import build_report
from restart_api import programs
from restart_api.ratelimit import limiter, write_limit
from restart_api.schemas import (
    MonteCarloRequest,
    MonteCarloResponse,
    RoutineSummary,
    SchemeSummary,
    SimulateRequest,
    SimulateResponse,
)
from restart_api.security import require_write_access

router = APIRouter(prefix="/setpieces", tags=["setpieces"])


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
    return programs.to_simulate_response(programs.ENGINE.run(program, req.seed))


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

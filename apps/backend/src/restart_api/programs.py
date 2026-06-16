"""Shared simulation wiring: engine, runner, catalog, and program builder.

Both the synchronous setpieces endpoints and the async job worker compile the
same way, so the engine/runner singletons, the routine/scheme catalog, and the
``build_program`` cache live here (DRY). The active xG model is injected once at
import; without it the engine uses the placeholder shot model (mean_xg = 0).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import HTTPException

from restart.engine import SetPieceEngine
from restart.montecarlo import MonteCarloRunner
from restart.players.player import PositionGroup
from restart.tactics.compile import Scenario, SimProgram, compile_scenario
from restart.tactics.library import all_corner_routines, all_schemes
from restart_api.deps import team_repository
from restart_api.jobs.runner import ProgressFn, run_batch
from restart_api.repositories.ports import SimRunRecord
from restart_api.xg import active_model_id, load_active_scorer

XG_MODEL_ID = active_model_id()
ENGINE = SetPieceEngine(xg_scorer=load_active_scorer())
RUNNER = MonteCarloRunner(ENGINE)


def _slug(name: str) -> str:
    return name.lower().replace(" ", "-")


ROUTINES = {_slug(r.name): r for r in all_corner_routines()}
SCHEMES = {_slug(s.name): s for s in all_schemes()}


@lru_cache(maxsize=128)
def build_program(
    routine_id: str, scheme_id: str, attacking_id: str, defending_id: str
) -> SimProgram:
    routine = ROUTINES.get(routine_id)
    scheme = SCHEMES.get(scheme_id)
    if routine is None:
        raise HTTPException(status_code=404, detail=f"unknown routine_id {routine_id!r}")
    if scheme is None:
        raise HTTPException(status_code=404, detail=f"unknown scheme_id {scheme_id!r}")
    teams = team_repository()
    attacking = teams.get(attacking_id)  # raises ValueError (-> 422) on unknown team
    defending = teams.get(defending_id)
    kicker = max(attacking.players, key=lambda p: p.attributes.delivery).player_id
    outfield = [
        p.player_id
        for p in attacking.players
        if p.position_group is not PositionGroup.GK and p.player_id != kicker
    ]
    roles = {a.role: outfield[i] for i, a in enumerate(routine.assignments)}
    return compile_scenario(
        Scenario(
            routine=routine,
            attacking_team=attacking,
            defending_team=defending,
            kicker_id=kicker,
            role_assignments=roles,
            scheme=scheme,
        )
    )


def program_from_spec(spec: dict[str, Any]) -> SimProgram:
    """Build a program from a stored scenario spec (the job worker's entrypoint)."""
    return build_program(
        spec["routine_id"], spec["scheme_id"], spec["attacking_team_id"], spec["defending_team_id"]
    )


def default_executor(run: SimRunRecord, progress: ProgressFn) -> dict[str, Any]:
    """The production job body: compile the run's scenario and execute the batch."""
    program = program_from_spec(run.spec)
    report, samples = run_batch(RUNNER, program, run.n_sims, run.root_seed, progress)
    return {**report, "xg_model": XG_MODEL_ID, "xg_samples": samples}

"""Asynchronous Monte Carlo sim runs (ADR-007 d3, doc 02 4.1).

POST enqueues a job (202) - or returns the existing run on an idempotency hit
(200); GET polls status/progress and, once complete, the aggregate result with
xG samples. The events endpoint replays a representative single sim (the
worst/median/best by xG) for the workbench Replay picker.
"""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from restart import ENGINE_VERSION
from restart_api import programs
from restart_api.deps import job_queue, scenario_repo, sim_run_repo
from restart_api.hashing import idempotency_key
from restart_api.jobs.queue import JobQueue
from restart_api.ratelimit import limiter, write_limit
from restart_api.repositories.ports import (
    STATUS_COMPLETE,
    ScenarioRepository,
    SimRunRecord,
    SimRunRepository,
)
from restart_api.schemas import SimRunCreate, SimRunResultDTO, SimRunStatusDTO, SimulateResponse
from restart_api.security import require_write_access

router = APIRouter(prefix="/sim-runs", tags=["sim-runs"])


def _to_status(run: SimRunRecord) -> SimRunStatusDTO:
    result = SimRunResultDTO(**run.result) if run.result else None
    return SimRunStatusDTO(
        run_id=run.run_id,
        scenario_id=run.scenario_id,
        status=run.status,
        progress=run.progress,
        n_sims=run.n_sims,
        root_seed=run.root_seed,
        engine_version=run.engine_version,
        created_at=run.created_at,
        result=result,
        error=run.error,
    )


@router.post(
    "",
    response_model=SimRunStatusDTO,
    status_code=202,
    dependencies=[Depends(require_write_access)],
)
@limiter.limit(write_limit)
async def create_sim_run(
    request: Request,
    response: Response,
    body: SimRunCreate,
    scenarios: ScenarioRepository = Depends(scenario_repo),  # noqa: B008
    runs: SimRunRepository = Depends(sim_run_repo),  # noqa: B008
    queue: JobQueue = Depends(job_queue),  # noqa: B008
) -> SimRunStatusDTO:
    scenario = scenarios.get(body.scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"unknown scenario {body.scenario_id!r}")

    # n_sims is part of the identity: a larger batch is a different result, so it
    # must not collide with a smaller prior run for the same spec + seed.
    key = idempotency_key({**scenario.spec, "n_sims": body.n_sims}, body.root_seed, ENGINE_VERSION)
    existing = runs.by_idempotency_key(key)
    if existing is not None:
        # Same spec + seed + engine -> return the existing run, never recompute.
        response.status_code = 200
        return _to_status(existing)

    run = SimRunRecord(
        run_id=str(uuid4()),
        scenario_id=scenario.scenario_id,
        idempotency_key=key,
        n_sims=body.n_sims,
        root_seed=body.root_seed,
        engine_version=ENGINE_VERSION,
        created_at=datetime.now(UTC).isoformat(),
        spec=scenario.spec,
    )
    runs.create(run)
    await queue.submit(run.run_id)
    return _to_status(run)


@router.get("/{run_id}", response_model=SimRunStatusDTO)
def get_sim_run(
    run_id: str,
    runs: SimRunRepository = Depends(sim_run_repo),  # noqa: B008
) -> SimRunStatusDTO:
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"unknown sim run {run_id!r}")
    return _to_status(run)


@router.get("/{run_id}/events", response_model=SimulateResponse)
def sim_run_events(
    run_id: str,
    sample: str = Query("median"),
    runs: SimRunRepository = Depends(sim_run_repo),  # noqa: B008
) -> SimulateResponse:
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"unknown sim run {run_id!r}")
    if run.status != STATUS_COMPLETE or not run.result:
        raise HTTPException(status_code=409, detail="run is not complete")
    seeds = run.result.get("replay_seeds", {})
    seed = seeds.get(sample, seeds.get("median"))
    if seed is None:
        raise HTTPException(status_code=409, detail="no replay seeds available")
    program = programs.program_from_spec(run.spec)
    return programs.to_simulate_response(programs.ENGINE.run(program, int(seed)))

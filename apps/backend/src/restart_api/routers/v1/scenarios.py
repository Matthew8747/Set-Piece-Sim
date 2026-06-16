"""Scenario persistence (ADR-007 d1/d3).

A scenario is a named, canonical spec (routine + scheme + the two squads). It is
validated against the catalog at create time and hashed for idempotency; sim
runs reference it by id.
"""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from restart_api import programs
from restart_api.deps import scenario_repo, team_repository
from restart_api.hashing import scenario_hash
from restart_api.ratelimit import limiter, write_limit
from restart_api.repositories.ports import ScenarioRecord, ScenarioRepository
from restart_api.schemas import ScenarioCreate, ScenarioDTO
from restart_api.security import require_write_access

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def _to_dto(rec: ScenarioRecord) -> ScenarioDTO:
    return ScenarioDTO(
        scenario_id=rec.scenario_id,
        name=rec.name,
        spec={k: str(v) for k, v in rec.spec.items()},
        scenario_hash=rec.scenario_hash,
        created_at=rec.created_at,
    )


def _validate(body: ScenarioCreate) -> None:
    if body.routine_id not in programs.ROUTINES:
        raise HTTPException(status_code=404, detail=f"unknown routine_id {body.routine_id!r}")
    if body.scheme_id not in programs.SCHEMES:
        raise HTTPException(status_code=404, detail=f"unknown scheme_id {body.scheme_id!r}")
    teams = {t.team_id for t in team_repository().list_teams()}
    for tid in (body.attacking_team_id, body.defending_team_id):
        if tid not in teams:
            raise HTTPException(status_code=404, detail=f"unknown team {tid!r}")


@router.post(
    "", response_model=ScenarioDTO, status_code=201, dependencies=[Depends(require_write_access)]
)
@limiter.limit(write_limit)
def create_scenario(
    request: Request,
    body: ScenarioCreate,
    repo: ScenarioRepository = Depends(scenario_repo),  # noqa: B008
) -> ScenarioDTO:
    _validate(body)
    spec = {
        "routine_id": body.routine_id,
        "scheme_id": body.scheme_id,
        "attacking_team_id": body.attacking_team_id,
        "defending_team_id": body.defending_team_id,
    }
    rec = ScenarioRecord(
        scenario_id=str(uuid4()),
        name=body.name,
        spec=spec,
        scenario_hash=scenario_hash(spec),
        created_at=datetime.now(UTC).isoformat(),
    )
    return _to_dto(repo.create(rec))


@router.get("", response_model=list[ScenarioDTO])
def list_scenarios(
    repo: ScenarioRepository = Depends(scenario_repo),  # noqa: B008
) -> list[ScenarioDTO]:
    return [_to_dto(r) for r in repo.list(limit=100)]


@router.get("/{scenario_id}", response_model=ScenarioDTO)
def get_scenario(
    scenario_id: str,
    repo: ScenarioRepository = Depends(scenario_repo),  # noqa: B008
) -> ScenarioDTO:
    rec = repo.get(scenario_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"unknown scenario {scenario_id!r}")
    return _to_dto(rec)

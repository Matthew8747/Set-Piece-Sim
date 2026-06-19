"""Repository ports (Protocols) + the records they persist (ADR-007 d1).

Records are plain dataclasses (JSON-friendly), deliberately decoupled from the
pydantic request/response DTOs so the storage layer does not depend on the web
layer. Adapters: file (default) and Postgres (drop-in).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from restart.players.team import Team
from restart_api.squads.loader import TeamSummary

# Sim-run lifecycle states.
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETE = "complete"
STATUS_FAILED = "failed"


@dataclass(frozen=True)
class ScenarioRecord:
    scenario_id: str
    name: str
    spec: dict[str, Any]  # canonical scenario spec (routine/scheme/teams/edits)
    scenario_hash: str
    created_at: str  # ISO-8601 UTC


@dataclass
class SimRunRecord:
    """A Monte Carlo job. Mutable: the worker updates status/progress/result."""

    run_id: str
    scenario_id: str
    idempotency_key: str
    n_sims: int
    root_seed: int
    engine_version: str
    status: str = STATUS_QUEUED
    progress: float = 0.0
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: str = ""
    spec: dict[str, Any] = field(default_factory=dict)  # snapshot for the worker


class TeamRepository(Protocol):
    def list_teams(self) -> list[TeamSummary]: ...
    def get(self, team_id: str) -> Team: ...


class ScenarioRepository(Protocol):
    def create(self, rec: ScenarioRecord) -> ScenarioRecord: ...
    def get(self, scenario_id: str) -> ScenarioRecord | None: ...
    def list(self, limit: int) -> list[ScenarioRecord]: ...


class SimRunRepository(Protocol):
    def create(self, run: SimRunRecord) -> SimRunRecord: ...
    def get(self, run_id: str) -> SimRunRecord | None: ...
    def by_idempotency_key(self, key: str) -> SimRunRecord | None: ...
    def update(self, run: SimRunRecord) -> None: ...

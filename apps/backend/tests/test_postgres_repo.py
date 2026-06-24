"""Postgres repository round-trip - skipped unless a server is provided (ADR-007 d1).

Mirrors the file-adapter contract against the Postgres drop-in. Set
``RESTART_TEST_DATABASE_URL`` to a throwaway database to run it; CI stays
server-free.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from restart import ENGINE_VERSION
from restart_api.repositories.ports import ScenarioRecord, SimRunRecord

pytestmark = pytest.mark.postgres

DSN = os.environ.get("RESTART_TEST_DATABASE_URL")
requires_pg = pytest.mark.skipif(not DSN, reason="no RESTART_TEST_DATABASE_URL")


@requires_pg
def test_scenario_and_sim_run_round_trip() -> None:
    assert DSN is not None
    pytest.importorskip("psycopg")
    from restart_api.repositories.postgres import (
        PostgresScenarioRepository,
        PostgresSimRunRepository,
    )

    scenarios = PostgresScenarioRepository(DSN)
    rec = ScenarioRecord(
        scenario_id=str(uuid4()),
        name="round-trip",
        spec={"routine_id": "r", "scheme_id": "s"},
        scenario_hash="hash",
        created_at=datetime.now(UTC).isoformat(),
    )
    scenarios.create(rec)
    assert scenarios.get(rec.scenario_id) == rec

    runs = PostgresSimRunRepository(DSN)
    run = SimRunRecord(
        run_id=str(uuid4()),
        scenario_id=rec.scenario_id,
        idempotency_key=str(uuid4()),
        n_sims=10,
        root_seed=1,
        engine_version=ENGINE_VERSION,
        created_at=datetime.now(UTC).isoformat(),
        spec=rec.spec,
    )
    runs.create(run)
    hit = runs.by_idempotency_key(run.idempotency_key)
    assert hit is not None and hit.run_id == run.run_id

    run.status = "complete"
    run.progress = 1.0
    run.result = {"p_goal": 0.1}
    runs.update(run)
    got = runs.get(run.run_id)
    assert got is not None and got.status == "complete" and got.result == {"p_goal": 0.1}

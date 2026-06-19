"""Postgres repository adapters — drop-ins for the file defaults (ADR-007 d1).

Same Protocols as ``repositories.file``; selected at runtime when
``RESTART_DATABASE_URL`` is set. A connection is opened per operation (simple and
correct; a real deployment can pool). Spec/result/error travel as JSON text, so
the schema matches the SQLite adapter row-for-row.

``psycopg`` is the optional ``restart-backend[postgres]`` extra, imported lazily,
so the default install + CI stay server-free. Tests are marked ``postgres`` and
skip unless ``RESTART_TEST_DATABASE_URL`` is set.
"""

from __future__ import annotations

import json
from typing import Any

from restart_api.repositories.ports import ScenarioRecord, SimRunRecord

_SCENARIOS_DDL = (
    "CREATE TABLE IF NOT EXISTS scenarios ("
    "scenario_id TEXT PRIMARY KEY, name TEXT NOT NULL, spec_json TEXT NOT NULL, "
    "scenario_hash TEXT NOT NULL, created_at TEXT NOT NULL)"
)
_SIM_RUNS_DDL = (
    "CREATE TABLE IF NOT EXISTS sim_runs ("
    "run_id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, "
    "idempotency_key TEXT NOT NULL UNIQUE, n_sims INTEGER NOT NULL, "
    "root_seed BIGINT NOT NULL, engine_version TEXT NOT NULL, status TEXT NOT NULL, "
    "progress DOUBLE PRECISION NOT NULL, result_json TEXT, error_json TEXT, "
    "created_at TEXT NOT NULL, spec_json TEXT NOT NULL)"
)


def _connect(dsn: str) -> Any:
    import psycopg

    return psycopg.connect(dsn)


def _dump(value: dict[str, Any] | None) -> str | None:
    return json.dumps(value) if value is not None else None


def _load(value: str | None) -> dict[str, Any] | None:
    return json.loads(value) if value else None


class PostgresScenarioRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        with _connect(dsn) as conn:
            conn.execute(_SCENARIOS_DDL)
            conn.commit()

    def create(self, rec: ScenarioRecord) -> ScenarioRecord:
        with _connect(self._dsn) as conn:
            conn.execute(
                "INSERT INTO scenarios VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (scenario_id) DO UPDATE SET "
                "name = EXCLUDED.name, spec_json = EXCLUDED.spec_json, "
                "scenario_hash = EXCLUDED.scenario_hash, created_at = EXCLUDED.created_at",
                (
                    rec.scenario_id,
                    rec.name,
                    json.dumps(rec.spec),
                    rec.scenario_hash,
                    rec.created_at,
                ),
            )
            conn.commit()
        return rec

    def get(self, scenario_id: str) -> ScenarioRecord | None:
        with _connect(self._dsn) as conn:
            row = conn.execute(
                "SELECT scenario_id, name, spec_json, scenario_hash, created_at "
                "FROM scenarios WHERE scenario_id = %s",
                (scenario_id,),
            ).fetchone()
        return _row_to_scenario(row) if row else None

    def list(self, limit: int) -> list[ScenarioRecord]:
        with _connect(self._dsn) as conn:
            rows = conn.execute(
                "SELECT scenario_id, name, spec_json, scenario_hash, created_at "
                "FROM scenarios ORDER BY created_at DESC LIMIT %s",
                (limit,),
            ).fetchall()
        return [_row_to_scenario(r) for r in rows]


class PostgresSimRunRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        with _connect(dsn) as conn:
            conn.execute(_SIM_RUNS_DDL)
            conn.commit()

    def create(self, run: SimRunRecord) -> SimRunRecord:
        with _connect(self._dsn) as conn:
            conn.execute(
                "INSERT INTO sim_runs VALUES " "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    run.run_id,
                    run.scenario_id,
                    run.idempotency_key,
                    run.n_sims,
                    run.root_seed,
                    run.engine_version,
                    run.status,
                    run.progress,
                    _dump(run.result),
                    _dump(run.error),
                    run.created_at,
                    json.dumps(run.spec),
                ),
            )
            conn.commit()
        return run

    def get(self, run_id: str) -> SimRunRecord | None:
        with _connect(self._dsn) as conn:
            row = conn.execute(_RUN_SELECT + " WHERE run_id = %s", (run_id,)).fetchone()
        return _row_to_run(row) if row else None

    def by_idempotency_key(self, key: str) -> SimRunRecord | None:
        with _connect(self._dsn) as conn:
            row = conn.execute(_RUN_SELECT + " WHERE idempotency_key = %s", (key,)).fetchone()
        return _row_to_run(row) if row else None

    def update(self, run: SimRunRecord) -> None:
        with _connect(self._dsn) as conn:
            conn.execute(
                "UPDATE sim_runs SET status = %s, progress = %s, result_json = %s, "
                "error_json = %s WHERE run_id = %s",
                (run.status, run.progress, _dump(run.result), _dump(run.error), run.run_id),
            )
            conn.commit()


_RUN_SELECT = (
    "SELECT run_id, scenario_id, idempotency_key, n_sims, root_seed, engine_version, "
    "status, progress, result_json, error_json, created_at, spec_json FROM sim_runs"
)


def _row_to_scenario(row: Any) -> ScenarioRecord:
    return ScenarioRecord(
        scenario_id=row[0],
        name=row[1],
        spec=json.loads(row[2]),
        scenario_hash=row[3],
        created_at=row[4],
    )


def _row_to_run(row: Any) -> SimRunRecord:
    return SimRunRecord(
        run_id=row[0],
        scenario_id=row[1],
        idempotency_key=row[2],
        n_sims=row[3],
        root_seed=row[4],
        engine_version=row[5],
        status=row[6],
        progress=row[7],
        result=_load(row[8]),
        error=_load(row[9]),
        created_at=row[10],
        spec=json.loads(row[11]),
    )

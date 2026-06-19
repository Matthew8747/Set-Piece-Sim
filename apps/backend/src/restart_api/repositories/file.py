"""File-based repository adapters — the server-free default (ADR-007 d1).

Teams come from the marts (read-only); scenarios and sim-runs persist to a
single SQLite file. A fresh connection is opened per operation (cheap, and
avoids cross-thread issues when the in-process worker runs on a threadpool);
WAL mode keeps reads and the worker's progress writes from blocking each other.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from restart.players.team import Team
from restart_api.repositories.ports import ScenarioRecord, SimRunRecord
from restart_api.squads.loader import MartSquadLoader, TeamSummary


class MartTeamRepository:
    """TeamRepository backed by the committed marts."""

    def __init__(self, marts_dir: Path) -> None:
        self._loader = MartSquadLoader(marts_dir)

    def list_teams(self) -> list[TeamSummary]:
        return self._loader.list_teams()

    def get(self, team_id: str) -> Team:
        return self._loader.team_by_id(team_id)


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.row_factory = sqlite3.Row
    return con


class SqliteScenarioRepository:
    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        with closing(_connect(self._path)) as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS scenarios ("
                "scenario_id TEXT PRIMARY KEY, name TEXT NOT NULL, spec_json TEXT NOT NULL, "
                "scenario_hash TEXT NOT NULL, created_at TEXT NOT NULL)"
            )
            con.commit()

    def create(self, rec: ScenarioRecord) -> ScenarioRecord:
        with closing(_connect(self._path)) as con:
            con.execute(
                "INSERT OR REPLACE INTO scenarios VALUES (?, ?, ?, ?, ?)",
                (
                    rec.scenario_id,
                    rec.name,
                    json.dumps(rec.spec),
                    rec.scenario_hash,
                    rec.created_at,
                ),
            )
            con.commit()
        return rec

    def get(self, scenario_id: str) -> ScenarioRecord | None:
        with closing(_connect(self._path)) as con:
            row = con.execute(
                "SELECT * FROM scenarios WHERE scenario_id = ?", (scenario_id,)
            ).fetchone()
        return _to_scenario(row) if row else None

    def list(self, limit: int) -> list[ScenarioRecord]:
        with closing(_connect(self._path)) as con:
            rows = con.execute(
                "SELECT * FROM scenarios ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_to_scenario(r) for r in rows]


class SqliteSimRunRepository:
    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        with closing(_connect(self._path)) as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS sim_runs ("
                "run_id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, "
                "idempotency_key TEXT NOT NULL UNIQUE, n_sims INTEGER NOT NULL, "
                "root_seed INTEGER NOT NULL, engine_version TEXT NOT NULL, status TEXT NOT NULL, "
                "progress REAL NOT NULL, result_json TEXT, error_json TEXT, "
                "created_at TEXT NOT NULL, spec_json TEXT NOT NULL)"
            )
            con.commit()

    def create(self, run: SimRunRecord) -> SimRunRecord:
        with closing(_connect(self._path)) as con:
            con.execute(
                "INSERT INTO sim_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            con.commit()
        return run

    def get(self, run_id: str) -> SimRunRecord | None:
        with closing(_connect(self._path)) as con:
            row = con.execute("SELECT * FROM sim_runs WHERE run_id = ?", (run_id,)).fetchone()
        return _to_run(row) if row else None

    def by_idempotency_key(self, key: str) -> SimRunRecord | None:
        with closing(_connect(self._path)) as con:
            row = con.execute("SELECT * FROM sim_runs WHERE idempotency_key = ?", (key,)).fetchone()
        return _to_run(row) if row else None

    def update(self, run: SimRunRecord) -> None:
        with closing(_connect(self._path)) as con:
            con.execute(
                "UPDATE sim_runs SET status = ?, progress = ?, result_json = ?, error_json = ? "
                "WHERE run_id = ?",
                (run.status, run.progress, _dump(run.result), _dump(run.error), run.run_id),
            )
            con.commit()


def _dump(value: dict[str, object] | None) -> str | None:
    return json.dumps(value) if value is not None else None


def _load(value: str | None) -> dict[str, object] | None:
    return json.loads(value) if value else None


def _to_scenario(row: sqlite3.Row) -> ScenarioRecord:
    return ScenarioRecord(
        scenario_id=row["scenario_id"],
        name=row["name"],
        spec=json.loads(row["spec_json"]),
        scenario_hash=row["scenario_hash"],
        created_at=row["created_at"],
    )


def _to_run(row: sqlite3.Row) -> SimRunRecord:
    return SimRunRecord(
        run_id=row["run_id"],
        scenario_id=row["scenario_id"],
        idempotency_key=row["idempotency_key"],
        n_sims=row["n_sims"],
        root_seed=row["root_seed"],
        engine_version=row["engine_version"],
        status=row["status"],
        progress=row["progress"],
        result=_load(row["result_json"]),
        error=_load(row["error_json"]),
        created_at=row["created_at"],
        spec=json.loads(row["spec_json"]),
    )

"""Repository ports + file adapters (ADR-007 d1).

The default adapters are server-free: scenarios persist to SQLite, teams come
from the marts. The same Protocols are implemented by the Postgres drop-ins
(tested separately, skipped without a server).
"""

from datetime import UTC, datetime
from pathlib import Path

from restart.players.team import Team
from restart_api.repositories.file import (
    MartTeamRepository,
    SqliteScenarioRepository,
)
from restart_api.repositories.ports import ScenarioRecord
from restart_api.squads.loader import team_slug

MARTS = Path(__file__).resolve().parents[3] / "data" / "marts"


def _record(scenario_id: str = "sc-1") -> ScenarioRecord:
    return ScenarioRecord(
        scenario_id=scenario_id,
        name="England corners vs Argentina",
        spec={"routine_id": "r", "scheme_id": "s", "attacking_team_id": "england"},
        scenario_hash="deadbeef",
        created_at=datetime.now(UTC).isoformat(),
    )


def test_scenario_round_trips(tmp_path: Path) -> None:
    repo = SqliteScenarioRepository(tmp_path / "app.sqlite")
    saved = repo.create(_record())
    loaded = repo.get(saved.scenario_id)
    assert loaded is not None
    assert loaded.name == "England corners vs Argentina"
    assert loaded.spec["attacking_team_id"] == "england"
    assert loaded.scenario_hash == "deadbeef"


def test_scenario_get_missing_returns_none(tmp_path: Path) -> None:
    repo = SqliteScenarioRepository(tmp_path / "app.sqlite")
    assert repo.get("nope") is None


def test_scenario_list_newest_first(tmp_path: Path) -> None:
    repo = SqliteScenarioRepository(tmp_path / "app.sqlite")
    repo.create(_record("sc-1"))
    repo.create(_record("sc-2"))
    ids = [r.scenario_id for r in repo.list(limit=10)]
    assert set(ids) == {"sc-1", "sc-2"}


def test_team_repository_lists_and_gets(tmp_path: Path) -> None:
    repo = MartTeamRepository(MARTS)
    summaries = repo.list_teams()
    assert any(s.team_id == team_slug("England") for s in summaries)
    team = repo.get(team_slug("England"))
    assert isinstance(team, Team)
    assert len(team.players) == 11

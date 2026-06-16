"""Real-squad endpoints + sim path on real squads (ADR-007 d2).

Demo squads are retired from the API runtime: /teams and /players expose the
mart-derived squads, and the simulate/montecarlo endpoints run them.
"""

from fastapi.testclient import TestClient

from restart_api.main import create_app
from restart_api.settings import Settings

CLIENT = TestClient(create_app(Settings(app_env="test")), raise_server_exceptions=False)
_RID = CLIENT.get("/api/v1/setpieces/routines").json()[0]["routine_id"]
_SID = CLIENT.get("/api/v1/setpieces/schemes").json()[0]["scheme_id"]


def test_list_teams_returns_real_nations() -> None:
    teams = CLIENT.get("/api/v1/teams").json()
    ids = {t["team_id"] for t in teams}
    assert "england" in ids and "argentina" in ids
    assert all(t["n_players"] >= 11 for t in teams)


def test_players_endpoint_returns_xi_with_provenance() -> None:
    r = CLIENT.get("/api/v1/players", params={"team": "england"})
    assert r.status_code == 200
    players = r.json()
    assert len(players) == 11
    assert all(p["source"] for p in players)
    # Real identities, not synthetic demo names.
    assert all(not p["display_name"].startswith("England Player") for p in players)


def test_players_unknown_team_is_problem_json() -> None:
    r = CLIENT.get("/api/v1/players", params={"team": "atlantis"})
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")


def test_montecarlo_runs_on_real_squads_by_default() -> None:
    body = {"routine_id": _RID, "scheme_id": _SID, "n_sims": 8, "root_seed": 3}
    r = CLIENT.post("/api/v1/setpieces/montecarlo", json=body)
    assert r.status_code == 200
    assert r.json()["n_sims"] == 8


def test_explicit_team_ids_are_deterministic() -> None:
    body = {
        "routine_id": _RID,
        "scheme_id": _SID,
        "attacking_team_id": "england",
        "defending_team_id": "argentina",
        "seed": 5,
    }
    a = CLIENT.post("/api/v1/setpieces/simulate", json=body).json()
    b = CLIENT.post("/api/v1/setpieces/simulate", json=body).json()
    assert a["outcome"] == b["outcome"]
    assert a["events"] == b["events"]

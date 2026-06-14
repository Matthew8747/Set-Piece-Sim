"""Set-piece MVP endpoint tests (catalog, simulate, montecarlo)."""

from fastapi.testclient import TestClient

from restart_api.main import create_app

CLIENT = TestClient(create_app())


def _ids() -> tuple[str, str]:
    rid = CLIENT.get("/api/v1/setpieces/routines").json()[0]["routine_id"]
    sid = CLIENT.get("/api/v1/setpieces/schemes").json()[0]["scheme_id"]
    return rid, sid


class TestCatalog:
    def test_routines_listed(self) -> None:
        resp = CLIENT.get("/api/v1/setpieces/routines")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 5
        assert all({"routine_id", "name", "set_piece"} <= set(r) for r in body)

    def test_schemes_listed(self) -> None:
        resp = CLIENT.get("/api/v1/setpieces/schemes")
        assert resp.status_code == 200
        assert len(resp.json()) == 3


class TestSimulate:
    def test_simulate_returns_outcome_and_replay(self) -> None:
        rid, sid = _ids()
        resp = CLIENT.post(
            "/api/v1/setpieces/simulate",
            json={"routine_id": rid, "scheme_id": sid, "seed": 7},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["outcome"]
        assert body["events"][0]["kind"] == "launch"
        assert body["engine_version"].startswith("sim/")
        # Replay payloads shaped for the frontend pitch.
        assert len(body["att_tracks"]) == len(body["track_times_s"])
        assert len(body["ball_path"]) > 0

    def test_simulate_deterministic_over_http(self) -> None:
        rid, sid = _ids()
        payload = {"routine_id": rid, "scheme_id": sid, "seed": 11}
        a = CLIENT.post("/api/v1/setpieces/simulate", json=payload).json()
        b = CLIENT.post("/api/v1/setpieces/simulate", json=payload).json()
        assert a["outcome"] == b["outcome"]
        assert [e["kind"] for e in a["events"]] == [e["kind"] for e in b["events"]]

    def test_unknown_routine_404(self) -> None:
        _, sid = _ids()
        resp = CLIENT.post(
            "/api/v1/setpieces/simulate",
            json={"routine_id": "does-not-exist", "scheme_id": sid},
        )
        assert resp.status_code == 404


class TestMonteCarlo:
    def test_montecarlo_returns_cis(self) -> None:
        rid, sid = _ids()
        resp = CLIENT.post(
            "/api/v1/setpieces/montecarlo",
            json={"routine_id": rid, "scheme_id": sid, "n_sims": 30, "root_seed": 1},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["n_sims"] == 30
        goal = body["p_goal"]
        assert goal["lo"] <= goal["p"] <= goal["hi"]
        assert sum(body["outcome_counts"].values()) == 30

    def test_n_sims_upper_bound_enforced(self) -> None:
        rid, sid = _ids()
        resp = CLIENT.post(
            "/api/v1/setpieces/montecarlo",
            json={"routine_id": rid, "scheme_id": sid, "n_sims": 999999},
        )
        assert resp.status_code == 422  # cost-bomb protection

    def test_montecarlo_reports_real_data_xg(self) -> None:
        """Phase-4 acceptance: a corner batch reports mean xG from the active
        real-data model (the model is committed under models/)."""
        rid, sid = _ids()
        resp = CLIENT.post(
            "/api/v1/setpieces/montecarlo",
            json={"routine_id": rid, "scheme_id": sid, "n_sims": 60, "root_seed": 2},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "mean_xg" in body and 0.0 <= body["mean_xg"] <= 1.0
        # A model is wired in this build, so shots carry an xG and it is named.
        assert body["xg_model"] == "xg-v1"
        assert body["n_xg_scored"] >= 0

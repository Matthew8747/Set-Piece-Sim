"""API-key write access + demo-mode bounds (ADR-007 d5, doc 02 9)."""

from fastapi.testclient import TestClient

from restart_api.main import create_app
from restart_api.settings import Settings

# Derive valid catalog ids rather than hard-coding library slugs.
_CATALOG = TestClient(create_app(Settings(app_env="test")))
_RID = _CATALOG.get("/api/v1/setpieces/routines").json()[0]["routine_id"]
_SID = _CATALOG.get("/api/v1/setpieces/schemes").json()[0]["scheme_id"]
_BODY = {"routine_id": _RID, "scheme_id": _SID, "n_sims": 1, "root_seed": 1}


def _keyed_client() -> TestClient:
    return TestClient(
        create_app(Settings(app_env="test", api_key="s3cret")), raise_server_exceptions=False
    )


def _demo_client() -> TestClient:
    return TestClient(create_app(Settings(app_env="test")), raise_server_exceptions=False)


def test_write_without_key_rejected_when_key_configured() -> None:
    r = _keyed_client().post("/api/v1/setpieces/montecarlo", json=_BODY)
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["status"] == 401


def test_write_with_wrong_key_rejected() -> None:
    r = _keyed_client().post(
        "/api/v1/setpieces/montecarlo", json=_BODY, headers={"X-API-Key": "nope"}
    )
    assert r.status_code == 401


def test_write_with_correct_key_allowed() -> None:
    r = _keyed_client().post(
        "/api/v1/setpieces/montecarlo", json=_BODY, headers={"X-API-Key": "s3cret"}
    )
    assert r.status_code == 200
    assert r.json()["n_sims"] == 1


def test_demo_mode_allows_bounded_write_without_key() -> None:
    r = _demo_client().post("/api/v1/setpieces/montecarlo", json=_BODY)
    assert r.status_code == 200


def test_demo_mode_still_enforces_bounds() -> None:
    body = {**_BODY, "n_sims": 999_999}
    r = _demo_client().post("/api/v1/setpieces/montecarlo", json=body)
    assert r.status_code == 422

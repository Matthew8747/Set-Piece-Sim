"""RFC 9457 problem-details responses (ADR-007 d5).

Every error the API surfaces must be ``application/problem+json`` with the
documented shape, so clients (and the generated TS types) have one error
contract instead of FastAPI's default ad-hoc bodies.
"""

from fastapi.testclient import TestClient

from restart_api.main import create_app
from restart_api.settings import Settings

client = TestClient(create_app(Settings(app_env="test")), raise_server_exceptions=False)


def test_validation_error_is_problem_json() -> None:
    # n_sims above the schema bound -> request validation failure.
    r = client.post(
        "/api/v1/setpieces/montecarlo",
        json={"routine_id": "x", "scheme_id": "y", "n_sims": 999_999},
    )
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["status"] == 422
    assert body["title"]
    assert body["type"]
    # Field-level errors are carried so a form UI can highlight them.
    assert isinstance(body["errors"], list) and body["errors"]


def test_unknown_routine_is_problem_json() -> None:
    r = client.post(
        "/api/v1/setpieces/montecarlo",
        json={"routine_id": "nope", "scheme_id": "nope", "n_sims": 1},
    )
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["status"] == 404
    assert "nope" in body["detail"]

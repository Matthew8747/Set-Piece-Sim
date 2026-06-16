"""Per-IP rate limiting (ADR-007 d5).

The limiter is a process-wide singleton, so each test saves/restores the
settings holder and clears buckets to stay hermetic.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from restart_api import ratelimit
from restart_api.main import create_app
from restart_api.settings import Settings


@pytest.fixture
def low_read_limit_client() -> Iterator[TestClient]:
    saved = ratelimit._settings
    cfg = Settings(app_env="test", rate_limit_read="3/minute")
    app = create_app(cfg)  # configure() points the limiter at cfg
    ratelimit.reset_for_tests()
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        ratelimit._settings = saved
        ratelimit.reset_for_tests()


def test_global_read_limit_returns_problem_json(low_read_limit_client: TestClient) -> None:
    # 3/minute -> the 4th request in the window is rejected.
    codes = [low_read_limit_client.get("/healthz").status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200]
    assert codes[3] == 429

    r = low_read_limit_client.get("/healthz")
    assert r.status_code == 429
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["status"] == 429
    assert body["title"] == "Too Many Requests"


def test_rate_limit_disabled_allows_unbounded() -> None:
    saved = ratelimit._settings
    cfg = Settings(app_env="test", rate_limit_read="2/minute", rate_limit_enabled=False)
    app = create_app(cfg)
    ratelimit.reset_for_tests()
    try:
        client = TestClient(app)
        codes = [client.get("/healthz").status_code for _ in range(5)]
        assert codes == [200] * 5
    finally:
        ratelimit._settings = saved
        ratelimit.reset_for_tests()

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


def test_sim_run_status_poll_is_exempt_from_read_limit(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Polling a run's status must not exhaust the global read bucket.

    The client polls every 400 ms (150/min), above the 120/min read default; a
    404 status poll still exercises the same middleware path as a real one, so if
    the endpoint were counted it would 429 well before a long run finished. A
    generic read must still be limited, proving the exemption is targeted.
    """
    saved = ratelimit._settings
    cfg = Settings(app_env="test", rate_limit_read="3/minute", data_dir=tmp_path)
    app = create_app(cfg)
    ratelimit.reset_for_tests()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        poll_codes = [client.get("/api/v1/sim-runs/does-not-exist").status_code for _ in range(10)]
        assert poll_codes == [404] * 10, poll_codes  # never 429
        # A non-exempt read is still bounded by the same 3/minute bucket.
        read_codes = [client.get("/healthz").status_code for _ in range(5)]
        assert 429 in read_codes
    finally:
        ratelimit._settings = saved
        ratelimit.reset_for_tests()


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

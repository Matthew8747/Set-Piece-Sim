"""Shared backend test fixtures.

The rate limiter is a process-wide singleton (slowapi needs one to decorate
routes at import time), so its in-memory buckets are shared by every TestClient
in the run. Without a reset, write POSTs across the whole suite accumulate
toward the per-IP write limit and later tests start failing with 429 once the
suite grows (M3 adds many sim-run POSTs). Resetting before each test keeps every
test hermetic; tests that specifically exercise limits make all their calls
within a single test, so the reset never interferes with them.
"""

from pathlib import Path

import pytest

from restart_api import ratelimit


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> None:
    ratelimit.reset_for_tests()


# --- mart-dependent tests skip gracefully where the squad marts are absent ----
# The StatsBomb-derived marts are not committed (license), so they are missing in
# CI and on a fresh clone. The tests below read them (directly, or via an endpoint
# that loads real squads); without marts they should skip, not error. They still
# run locally once the ETL has populated data/marts.
_MARTS = Path(__file__).resolve().parents[3] / "data" / "marts"
_MARTS_PRESENT = (_MARTS / "mart_players.parquet").exists()

_MART_FILES = {"test_squads.py", "test_teams.py"}
_MART_NODES = (
    "test_scenarios.py::test_team_repository_lists_and_gets",
    "test_security.py::test_write_with_correct_key_allowed",
    "test_security.py::test_demo_mode_allows_bounded_write_without_key",
    "test_setpieces.py::TestSimulate::",
    "test_setpieces.py::TestMonteCarlo::",
    "test_sim_runs.py::test_scenario_create_and_fetch",
    "test_sim_runs.py::test_sim_run_lifecycle_and_result",
    "test_sim_runs.py::test_sim_run_idempotency_returns_existing",
    "test_sim_runs.py::test_replay_events_sample_picker",
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if _MARTS_PRESENT:
        return
    skip = pytest.mark.skip(
        reason="squad marts not provisioned (run the StatsBomb ETL); skipped where absent, e.g. CI"
    )
    for item in items:
        nid = item.nodeid.replace("\\", "/")
        fname = nid.split("::", 1)[0].rsplit("/", 1)[-1]
        if fname in _MART_FILES or any(tok in nid for tok in _MART_NODES):
            item.add_marker(skip)

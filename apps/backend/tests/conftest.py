"""Shared backend test fixtures.

The rate limiter is a process-wide singleton (slowapi needs one to decorate
routes at import time), so its in-memory buckets are shared by every TestClient
in the run. Without a reset, write POSTs across the whole suite accumulate
toward the per-IP write limit and later tests start failing with 429 once the
suite grows (M3 adds many sim-run POSTs). Resetting before each test keeps every
test hermetic; tests that specifically exercise limits make all their calls
within a single test, so the reset never interferes with them.
"""

import pytest

from restart_api import ratelimit


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> None:
    ratelimit.reset_for_tests()

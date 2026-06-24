"""Arq queue smoke test - skipped unless a Redis server is provided (ADR-007 d2).

Set ``RESTART_TEST_REDIS_URL`` to exercise it; CI stays server-free. Asserts only
that ``submit`` enqueues a job without error (the worker process executes it).
"""

from __future__ import annotations

import asyncio
import os

import pytest

pytestmark = pytest.mark.redis

REDIS = os.environ.get("RESTART_TEST_REDIS_URL")
requires_redis = pytest.mark.skipif(not REDIS, reason="no RESTART_TEST_REDIS_URL")


@requires_redis
def test_submit_enqueues() -> None:
    assert REDIS is not None
    pytest.importorskip("arq")
    from restart_api.jobs.arq_queue import ArqJobQueue

    queue = ArqJobQueue(REDIS)
    asyncio.run(queue.submit("run-smoke-test"))

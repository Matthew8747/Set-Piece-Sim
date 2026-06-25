"""Arq/Redis job queue adapter - a drop-in for the in-process queue (ADR-007 d2).

Selected at runtime when ``RESTART_REDIS_URL`` is set. The API side only needs
``submit`` (enqueue to Redis); a separate worker process runs the batch:

    arq restart_api.jobs.arq_queue.WorkerSettings

``arq``/``redis`` are the optional ``restart-backend[arq]`` extra. This module is
imported only on the configured path (``main`` when a Redis URL is present, and a
``@pytest.mark.redis`` test that ``importorskip``s arq), so the default install +
CI stay server-free.
"""

from __future__ import annotations

import os
from typing import Any, ClassVar

import arq
from arq.connections import RedisSettings

from restart_api.jobs.queue import JobExecutor
from restart_api.repositories.ports import (
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_RUNNING,
    SimRunRepository,
)

_DEFAULT_REDIS = "redis://localhost:6379"


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(os.environ.get("RESTART_REDIS_URL", _DEFAULT_REDIS))


class ArqJobQueue:
    """JobQueue port backed by Arq/Redis; ``submit`` enqueues a job."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._pool: Any = None

    async def submit(self, run_id: str) -> None:
        if self._pool is None:
            self._pool = await arq.create_pool(RedisSettings.from_dsn(self._redis_url))
        await self._pool.enqueue_job("run_sim_job", run_id)


async def run_sim_job(ctx: dict[str, Any], run_id: str) -> None:
    """Worker body: mirror the in-process lifecycle (queued→running→complete)."""
    runs: SimRunRepository = ctx["runs"]
    executor: JobExecutor = ctx["executor"]
    run = runs.get(run_id)
    if run is None:
        return
    run.status = STATUS_RUNNING
    runs.update(run)

    def progress(done: int, total: int) -> None:
        run.progress = done / total if total else 0.0
        runs.update(run)

    try:
        run.result = executor(run, progress)
    except Exception as exc:  # persisted as a structured failure, never crashes the worker
        run.status = STATUS_FAILED
        run.error = {"type": type(exc).__name__, "detail": str(exc)}
        runs.update(run)
        return
    run.progress = 1.0
    run.status = STATUS_COMPLETE
    runs.update(run)


async def _on_startup(ctx: dict[str, Any]) -> None:
    # Build the same repo + executor the API uses, so the worker writes progress
    # where the API reads it (shared Postgres, or the shared SQLite file).
    from restart_api.programs import default_executor
    from restart_api.settings import get_settings

    cfg = get_settings()
    if cfg.database_url is not None:
        from restart_api.repositories.postgres import PostgresSimRunRepository

        ctx["runs"] = PostgresSimRunRepository(cfg.database_url.get_secret_value())
    else:
        from restart_api.repositories.file import SqliteSimRunRepository

        ctx["runs"] = SqliteSimRunRepository(cfg.app_db_path)
    ctx["executor"] = default_executor


class WorkerSettings:
    """Arq worker entrypoint: ``arq restart_api.jobs.arq_queue.WorkerSettings``."""

    functions: ClassVar[list[Any]] = [run_sim_job]
    on_startup: ClassVar[Any] = _on_startup
    redis_settings: ClassVar[Any] = _redis_settings()

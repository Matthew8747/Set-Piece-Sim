"""JobQueue port + in-process adapter (ADR-007 d3).

The in-process queue is the server-free default: each submitted run executes in
a background asyncio task, bounded by a concurrency semaphore (cost-bomb cap,
doc 02 9). The CPU-bound batch runs in a worker thread so the event loop keeps
serving requests; the executor reports progress through the SimRunRepository so
clients can poll. The Arq/Redis adapter (M7) implements the same ``submit``.

The job body is an injected ``JobExecutor`` so the queue is testable without the
engine (and so ``restart_opt`` / engine wiring never leaks into the queue).
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

from restart_api.jobs.runner import ProgressFn
from restart_api.repositories.ports import (
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_RUNNING,
    SimRunRecord,
    SimRunRepository,
)


class JobExecutor(Protocol):
    """A job body: given the run + a progress callback, return the result payload."""

    def __call__(self, run: SimRunRecord, progress: ProgressFn) -> dict[str, Any]: ...


class JobQueue(Protocol):
    async def submit(self, run_id: str) -> None: ...


class InProcessJobQueue:
    def __init__(
        self,
        runs: SimRunRepository,
        executor: JobExecutor,
        max_concurrent: int = 2,
    ) -> None:
        self._runs = runs
        self._executor = executor
        self._sem = asyncio.Semaphore(max_concurrent)
        self._tasks: set[asyncio.Task[None]] = set()

    async def submit(self, run_id: str) -> None:
        task = asyncio.create_task(self._run(run_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def join(self) -> None:
        """Await all in-flight jobs (graceful shutdown / test synchronization)."""
        while self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)

    async def _run(self, run_id: str) -> None:
        async with self._sem:
            run = self._runs.get(run_id)
            if run is None:
                return
            run.status = STATUS_RUNNING
            self._runs.update(run)

            def progress(done: int, total: int) -> None:
                run.progress = done / total if total else 0.0
                self._runs.update(run)

            try:
                # CPU-bound: run off the event loop so polling stays responsive.
                result = await asyncio.to_thread(self._executor, run, progress)
            except Exception as exc:
                run.status = STATUS_FAILED
                run.error = {"type": type(exc).__name__, "detail": str(exc)}
                self._runs.update(run)
                return
            run.result = result
            run.progress = 1.0
            run.status = STATUS_COMPLETE
            self._runs.update(run)

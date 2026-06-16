"""In-process JobQueue lifecycle + concurrency (ADR-007 d3).

A fast fake executor keeps these tests engine-free; the real executor is
covered by test_jobs (batch runner) and test_sim_runs (endpoint integration).
"""

import asyncio
import time
from datetime import UTC, datetime
from pathlib import Path

from restart_api.jobs.queue import InProcessJobQueue
from restart_api.jobs.runner import ProgressFn
from restart_api.repositories.file import SqliteSimRunRepository
from restart_api.repositories.ports import (
    STATUS_COMPLETE,
    STATUS_FAILED,
    SimRunRecord,
)


def _run(run_id: str = "run-1", key: str = "k1") -> SimRunRecord:
    return SimRunRecord(
        run_id=run_id,
        scenario_id="sc-1",
        idempotency_key=key,
        n_sims=10,
        root_seed=1,
        engine_version="sim/0.4.0",
        created_at=datetime.now(UTC).isoformat(),
        spec={"routine_id": "r", "scheme_id": "s"},
    )


def _ok_executor(run: SimRunRecord, progress: ProgressFn) -> dict[str, object]:
    progress(run.n_sims, run.n_sims)
    return {"mean_xg": 0.12, "xg_samples": [0.1, 0.2], "xg_model": None}


def _boom_executor(run: SimRunRecord, progress: ProgressFn) -> dict[str, object]:
    raise RuntimeError("kaboom")


def test_job_completes_and_persists_result(tmp_path: Path) -> None:
    repo = SqliteSimRunRepository(tmp_path / "app.sqlite")
    repo.create(_run())

    async def scenario() -> None:
        queue = InProcessJobQueue(repo, _ok_executor)
        await queue.submit("run-1")
        await queue.join()

    asyncio.run(scenario())
    done = repo.get("run-1")
    assert done is not None
    assert done.status == STATUS_COMPLETE
    assert done.progress == 1.0
    assert done.result == {"mean_xg": 0.12, "xg_samples": [0.1, 0.2], "xg_model": None}


def test_failed_job_captures_error(tmp_path: Path) -> None:
    repo = SqliteSimRunRepository(tmp_path / "app.sqlite")
    repo.create(_run())

    async def scenario() -> None:
        queue = InProcessJobQueue(repo, _boom_executor)
        await queue.submit("run-1")
        await queue.join()

    asyncio.run(scenario())
    failed = repo.get("run-1")
    assert failed is not None
    assert failed.status == STATUS_FAILED
    assert failed.error is not None
    assert failed.error["type"] == "RuntimeError"
    assert "kaboom" in failed.error["detail"]


def test_concurrency_cap_is_respected(tmp_path: Path) -> None:
    repo = SqliteSimRunRepository(tmp_path / "app.sqlite")
    for i in range(4):
        repo.create(_run(run_id=f"run-{i}", key=f"k{i}"))

    peak = 0
    active = 0

    def tracking_executor(run: SimRunRecord, progress: ProgressFn) -> dict[str, object]:
        nonlocal peak, active
        active += 1
        peak = max(peak, active)
        time.sleep(0.02)  # hold the slot so concurrent jobs actually overlap
        active -= 1
        return {"ok": True}

    async def scenario() -> None:
        queue = InProcessJobQueue(repo, tracking_executor, max_concurrent=2)
        for i in range(4):
            await queue.submit(f"run-{i}")
        await queue.join()

    asyncio.run(scenario())
    assert peak <= 2
    assert all(repo.get(f"run-{i}").status == STATUS_COMPLETE for i in range(4))  # type: ignore[union-attr]

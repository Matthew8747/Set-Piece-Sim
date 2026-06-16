"""Batch execution with progress + per-sim xG sampling (ADR-007 d3).

Wraps the pure ``MonteCarloRunner`` (which already derives stable per-sim seeds
and reports progress every 50 sims) and adds two job concerns: a progress
callback and a bounded, deterministically-sampled set of per-sim xG values for
the distribution charts. No IO — this stays pure compute so determinism holds.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from restart.montecarlo import BatchResult, MonteCarloRunner, build_report
from restart.tactics.compile import SimProgram

# (done, total) progress callback, shared by the runner, executors, and queue.
ProgressFn = Callable[[int, int], None]

# Enough points for a faithful histogram/ECDF without bloating the job payload.
MAX_XG_SAMPLES = 500


def per_sim_xg(batch: BatchResult) -> list[float]:
    """xG of each sim (sum over its shot events; 0.0 when no shot was taken).

    Mirrors the aggregate's mean_xg numerator, so the sample mean tracks the
    reported ``mean_xg``.
    """
    out: list[float] = []
    for result in batch.results:
        xg = 0.0
        for event in result.events:
            value = getattr(event, "xg", None)
            if value is not None:
                xg += float(value)
        out.append(xg)
    return out


def subsample(values: list[float], k: int, seed: int) -> list[float]:
    """Deterministically take at most ``k`` values (seeded by the run's seed).

    Returns all values when there are <= k; otherwise a seeded uniform subset in
    original order (so the empirical distribution is preserved, reproducibly).
    """
    if len(values) <= k:
        return list(values)
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(len(values), size=k, replace=False))
    return [values[int(i)] for i in idx]


def run_batch(
    runner: MonteCarloRunner,
    program: SimProgram,
    n_sims: int,
    root_seed: int,
    progress: ProgressFn | None = None,
) -> tuple[dict[str, Any], list[float]]:
    """Run a Monte Carlo batch; return (aggregate report dict, xG samples)."""
    batch = runner.run(program, n_sims, root_seed, on_progress=progress)
    report = build_report(batch)
    samples = subsample(per_sim_xg(batch), MAX_XG_SAMPLES, root_seed)
    return report.to_dict(), samples

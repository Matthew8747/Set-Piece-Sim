"""Batch executor over the set-piece engine.

Determinism contract: sim *i* of a batch with ``root_seed`` always receives
the same per-sim seed (SeedSequence-derived), independent of batch size or
execution order — so (program, root_seed, n) is fully reproducible and any
single sim can be replayed in isolation by its seed (ADR-003 d9).

Parallelism note (registered tradeoff): the Phase-2 engine is the readable
single-sim reference (~30-80 ms/sim). This runner is a sequential loop —
process-pool parallelism on Windows costs more in pickling/spawn than it buys
at MVP batch sizes, and the real throughput answer is the Phase-3 fused batch
kernel (ADR-003 d8), not worker pools around the reference engine. The
``sim_seed`` function is the stable seam either future path reuses.
"""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from restart.engine import SetPieceEngine, SetPieceResult
from restart.tactics.compile import SimProgram


def sim_seeds(root_seed: int, n: int) -> list[int]:
    """Stable per-sim seeds derived from the root seed (replayable singly)."""
    if root_seed < 0 or n <= 0:
        msg = f"root_seed must be >= 0 and n > 0, got {root_seed}, {n}"
        raise ValueError(msg)
    state = np.random.SeedSequence(root_seed).generate_state(n, dtype=np.uint32)
    return [int(s) for s in state]


@dataclass(frozen=True, slots=True)
class BatchResult:
    """All per-sim results of one Monte Carlo batch."""

    results: tuple[SetPieceResult, ...]
    root_seed: int

    @property
    def n_sims(self) -> int:
        return len(self.results)


class MonteCarloRunner:
    def __init__(self, engine: SetPieceEngine | None = None) -> None:
        self._engine = engine if engine is not None else SetPieceEngine()

    def run(
        self,
        program: SimProgram,
        n_sims: int,
        root_seed: int = 0,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> BatchResult:
        if not 1 <= n_sims <= 200_000:
            msg = f"n_sims must be in [1, 200000], got {n_sims}"
            raise ValueError(msg)
        seeds = sim_seeds(root_seed, n_sims)
        results: list[SetPieceResult] = []
        for i, seed in enumerate(seeds):
            results.append(self._engine.run(program, seed))
            if on_progress is not None and (i + 1) % 50 == 0:
                on_progress(i + 1, n_sims)
        return BatchResult(results=tuple(results), root_seed=root_seed)

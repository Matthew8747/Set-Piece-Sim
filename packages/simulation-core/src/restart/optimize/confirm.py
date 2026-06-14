"""Screen-then-confirm statistics (pure): mean-xG confidence intervals, the
common-random-numbers confirm stage, and the non-overlap decision rule.

The objective is mean xG per sim (a mean of bounded continuous values), so its
uncertainty is a CI on a mean (normal/large-sample), not a Wilson proportion CI.
The confirm stage re-evaluates the screen's top-k candidates at a large budget
using a *common root seed* (CRN): every candidate sees the identical stream of
per-sim seeds, so differences are signal, not seed luck (M-3, doc 06 sec3.2).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

from restart.domain.vectors import FloatArray
from restart.montecarlo.runner import BatchResult
from restart.simulation.events import ShotEvent


def mean_xg_samples(batch: BatchResult) -> FloatArray:
    """Per-sim xG contribution: the shot's xG, or 0.0 for a sim with no scored shot."""
    out = np.zeros(batch.n_sims, dtype=np.float64)
    for i, r in enumerate(batch.results):
        shot = next((e for e in r.events if isinstance(e, ShotEvent)), None)
        if shot is not None and shot.xg is not None:
            out[i] = shot.xg
    return out


def mean_ci(samples: FloatArray, alpha: float = 0.05) -> tuple[float, float, float]:
    """(mean, lo, hi) large-sample CI for the mean, clamped to the xG [0,1] range."""
    n = int(samples.shape[0])
    if n == 0:
        return 0.0, 0.0, 0.0
    mean = float(np.mean(samples))
    if n == 1:
        return mean, mean, mean
    se = float(np.std(samples, ddof=1)) / math.sqrt(n)
    z = float(norm.ppf(1.0 - alpha / 2.0))
    lo = max(0.0, mean - z * se)
    hi = min(1.0, mean + z * se)
    return mean, lo, hi


def beats_baseline(
    candidate: tuple[float, float, float], baseline: tuple[float, float, float]
) -> bool:
    """True if the candidate's mean-xG CI is strictly above the baseline's CI.

    Each argument is (mean, lo, hi). "Beats" = non-overlapping 95% CIs with the
    candidate higher (roadmap Phase-5 acceptance), the honest bar for a discovery.
    """
    cand_lo = candidate[1]
    base_hi = baseline[2]
    return cand_lo > base_hi


@dataclass(frozen=True, slots=True)
class ConfirmResult:
    """One confirmed candidate at the high (confirm) budget."""

    params: dict[str, object]
    mean_xg: float
    ci_lo: float
    ci_hi: float
    n_sims: int
    root_seed: int

    @property
    def ci(self) -> tuple[float, float, float]:
        return self.mean_xg, self.ci_lo, self.ci_hi


def confirm_candidates(
    make_samples: Callable[[Mapping[str, object], int, int], FloatArray],
    candidates: Sequence[Mapping[str, object]],
    n_confirm: int,
    root_seed: int,
) -> list[ConfirmResult]:
    """Re-evaluate each candidate at ``n_confirm`` sims with a common root seed.

    ``make_samples(params, n_sims, root_seed)`` returns the per-sim xG samples for
    one candidate (the driver wires this to an xG-enabled objective). All
    candidates share ``root_seed`` -> common random numbers across candidates.
    """
    results: list[ConfirmResult] = []
    for params in candidates:
        samples = make_samples(params, n_confirm, root_seed)
        mean, lo, hi = mean_ci(samples)
        results.append(
            ConfirmResult(
                params=dict(params),
                mean_xg=mean,
                ci_lo=lo,
                ci_hi=hi,
                n_sims=n_confirm,
                root_seed=root_seed,
            )
        )
    return results

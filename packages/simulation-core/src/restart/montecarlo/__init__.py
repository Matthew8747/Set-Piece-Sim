"""Monte Carlo layer: batch execution, statistics, reports (Phase 3).

Runs the Phase-2 SetPieceEngine across seeded Philox-derived streams and
aggregates outcomes into probabilities with Wilson confidence intervals
(SciPy, per ADR-001 — no hand-rolled statistics).
"""

from restart.montecarlo.aggregate import OutcomeStats, ProportionCI, aggregate
from restart.montecarlo.report import SimulationReport, build_report
from restart.montecarlo.runner import BatchResult, MonteCarloRunner

__all__ = [
    "BatchResult",
    "MonteCarloRunner",
    "OutcomeStats",
    "ProportionCI",
    "SimulationReport",
    "aggregate",
    "build_report",
]

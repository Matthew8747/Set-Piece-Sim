"""Simulation report: the serializable summary the API/UI consume."""

from dataclasses import dataclass
from typing import Any

from restart import ENGINE_VERSION
from restart.montecarlo.aggregate import OutcomeStats, ProportionCI, aggregate
from restart.montecarlo.runner import BatchResult


@dataclass(frozen=True, slots=True)
class SimulationReport:
    engine_version: str
    root_seed: int
    n_sims: int
    stats: OutcomeStats

    def to_dict(self) -> dict[str, Any]:
        def ci(v: ProportionCI) -> dict[str, float | int]:
            return {"p": v.p, "lo": v.lo, "hi": v.hi, "k": v.k, "n": v.n}

        s = self.stats
        return {
            "engine_version": self.engine_version,
            "root_seed": self.root_seed,
            "n_sims": self.n_sims,
            "p_goal": ci(s.p_goal),
            "p_shot": ci(s.p_shot),
            "p_header_shot": ci(s.p_header_shot),
            "p_first_contact_attack": ci(s.p_first_contact_attack),
            "p_clearance": ci(s.p_clearance),
            "p_possession_recovered": ci(s.p_possession_recovered),
            "outcome_counts": dict(s.outcome_counts),
        }


def build_report(batch: BatchResult) -> SimulationReport:
    return SimulationReport(
        engine_version=ENGINE_VERSION,
        root_seed=batch.root_seed,
        n_sims=batch.n_sims,
        stats=aggregate(batch),
    )

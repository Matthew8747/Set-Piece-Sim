"""Optimization extension points (Phase 3: interfaces ONLY, no algorithms).

The Phase-5 optimizers (Optuna TPE primary; CMA-ES/GA comparisons — design
doc 06 §3) plug in here. An Optuna objective is one lambda away:

    space = corner_delivery_space()
    objective = RoutineObjective(base_scenario, space, n_sims=500, root_seed=7)
    study.optimize(lambda t: -objective(
        {p.name: t.suggest_float(p.name, p.lo, p.hi) for p in space.params}
    ), n_trials=...)
"""

from restart.optimize.interfaces import (
    ContinuousParam,
    EvaluationResult,
    ObjectiveFunction,
    RoutineObjective,
    SearchSpace,
    corner_delivery_space,
)

__all__ = [
    "ContinuousParam",
    "EvaluationResult",
    "ObjectiveFunction",
    "RoutineObjective",
    "SearchSpace",
    "corner_delivery_space",
]

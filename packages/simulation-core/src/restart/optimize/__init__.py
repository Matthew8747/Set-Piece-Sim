"""Pure optimization domain: the genome, the objective, the confirm statistics,
and the anti-exploit guards.

The search algorithms (Optuna TPE primary; random-search baseline) live in the
``restart_opt`` package (design doc 06 sec3) and consume only this pure surface,
keeping the simulation core free of Optuna/ML/IO. An Optuna objective is one
adapter away:

    genome = CornerGenome()
    objective = RoutineObjective(base, genome, runner=xg_runner, n_sims=250, root_seed=7)
    study.optimize(lambda t: objective(suggest(t, genome.space)), n_trials=...)
"""

from restart.optimize.boundary import boundary_flags, face_validity_flags
from restart.optimize.confirm import (
    ConfirmResult,
    beats_baseline,
    confirm_candidates,
    mean_ci,
    mean_xg_samples,
)
from restart.optimize.genome import (
    ZONE_GRID,
    CategoricalParam,
    ContinuousParam,
    CornerGenome,
    DeliveryGenome,
    Genome,
    IntParam,
    Param,
    SearchSpace,
    corner_delivery_space,
)
from restart.optimize.objective import (
    EvaluationResult,
    ObjectiveFunction,
    RoutineObjective,
)

__all__ = [
    "ZONE_GRID",
    "CategoricalParam",
    "ConfirmResult",
    "ContinuousParam",
    "CornerGenome",
    "DeliveryGenome",
    "EvaluationResult",
    "Genome",
    "IntParam",
    "ObjectiveFunction",
    "Param",
    "RoutineObjective",
    "SearchSpace",
    "beats_baseline",
    "boundary_flags",
    "confirm_candidates",
    "corner_delivery_space",
    "face_validity_flags",
    "mean_ci",
    "mean_xg_samples",
]

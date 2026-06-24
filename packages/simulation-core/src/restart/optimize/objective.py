"""The optimizer objective: a genome -> mean-xG-per-sim scalar.

Pure and deterministic per (params, root_seed): the same genome and root seed
always produce the same value, so the driver can compare candidates under common
random numbers (M-3). The objective evaluates by building the genome's Scenario,
compiling it, running a Monte Carlo batch on an xG-enabled engine, and reporting
mean xG (doc 06 sec2.3). Counterattack risk is reported, not optimized - the
multi-objective extension is future work (doc 06 sec3.2).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from restart.montecarlo.aggregate import aggregate
from restart.montecarlo.runner import MonteCarloRunner
from restart.optimize.confirm import mean_ci, mean_xg_samples
from restart.optimize.genome import Genome, SearchSpace
from restart.simulation.events import SetPieceOutcome
from restart.tactics.compile import Scenario, compile_scenario

#: Outcomes where the defending side ends with (or controls) the ball - the
#: coarse counterattack-risk proxy. A read of existing outcomes: no engine change.
_DEFENSE_RECOVERY: frozenset[SetPieceOutcome] = frozenset(
    {
        SetPieceOutcome.CLEARED,
        SetPieceOutcome.KEEPER_CLAIM,
        SetPieceOutcome.SECOND_BALL_DEFENSE,
        SetPieceOutcome.SAVED,
    }
)


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    mean_xg: float  # the objective (higher is better)
    mean_xg_ci_lo: float
    mean_xg_ci_hi: float
    p_goal: float
    counterattack_risk: float  # reported, NOT optimized (doc 06 sec3.2)
    n_sims: int
    root_seed: int


@runtime_checkable
class ObjectiveFunction(Protocol):
    """What any Phase-5 optimizer needs: params in, scalar out (higher better).

    The argument is positional-only: any single-argument ``(mapping) -> float``
    callable is a valid objective (the driver passes a plain dict positionally),
    regardless of its parameter name.
    """

    def __call__(self, values: Mapping[str, object], /) -> float: ...


class RoutineObjective:
    """Concrete ObjectiveFunction: genome -> compile -> Monte Carlo -> mean xG.

    Deterministic per (values, root_seed): supports common random numbers across
    optimizer trials and the confirm stage (M-3). Infeasible genomes raise
    ``ValueError`` from the genome builder - the driver prunes the trial.
    """

    def __init__(
        self,
        base_scenario: Scenario,
        genome: Genome,
        runner: MonteCarloRunner | None = None,
        n_sims: int = 200,
        root_seed: int = 0,
    ) -> None:
        self._base = base_scenario
        self.genome = genome
        self._n = n_sims
        self._seed = root_seed
        self._runner = runner if runner is not None else MonteCarloRunner()

    @property
    def space(self) -> SearchSpace:
        return self.genome.space

    def evaluate(self, values: Mapping[str, object]) -> EvaluationResult:
        scenario = self.genome.to_scenario(self._base, values)
        program = compile_scenario(scenario)
        batch = self._runner.run(program, self._n, self._seed)
        stats = aggregate(batch)
        mean, lo, hi = mean_ci(mean_xg_samples(batch))
        recovered = sum(1 for r in batch.results if r.outcome in _DEFENSE_RECOVERY)
        n = batch.n_sims
        return EvaluationResult(
            mean_xg=mean,
            mean_xg_ci_lo=lo,
            mean_xg_ci_hi=hi,
            p_goal=stats.p_goal.p,
            counterattack_risk=(recovered / n if n else 0.0),
            n_sims=self._n,
            root_seed=self._seed,
        )

    def __call__(self, values: Mapping[str, object]) -> float:
        return self.evaluate(values).mean_xg

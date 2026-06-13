"""Optimizer-facing interfaces (no search algorithms here by phase rule).

Design contract (design review §1, ADR-004): the search space is a typed,
bounded subset of Routine Spec fields; evaluations are deterministic per
(params, root_seed) so optimizers can use common random numbers; infeasible
parameter combinations raise (the optimizer must learn real constraints).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from restart.montecarlo.aggregate import aggregate
from restart.montecarlo.runner import MonteCarloRunner
from restart.tactics.compile import Scenario, compile_scenario
from restart.tactics.routine import Delivery, PitchPoint


@dataclass(frozen=True, slots=True)
class ContinuousParam:
    name: str
    lo: float
    hi: float

    def clip_check(self, value: float) -> float:
        if not self.lo <= value <= self.hi:
            msg = f"param {self.name}={value} outside [{self.lo}, {self.hi}]"
            raise ValueError(msg)
        return value


@dataclass(frozen=True, slots=True)
class SearchSpace:
    """The optimizer's genome definition (continuous v1; categoricals join in
    Phase 5 with the full routine-mutation space)."""

    params: tuple[ContinuousParam, ...]

    def validate(self, values: Mapping[str, float]) -> dict[str, float]:
        unknown = set(values) - {p.name for p in self.params}
        if unknown:
            msg = f"unknown params: {sorted(unknown)}"
            raise ValueError(msg)
        return {p.name: p.clip_check(values[p.name]) for p in self.params if p.name in values}


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    objective: float  # higher is better (P(goal))
    n_sims: int
    root_seed: int


@runtime_checkable
class ObjectiveFunction(Protocol):
    """What any Phase-5 optimizer needs: params in, scalar out."""

    def __call__(self, values: Mapping[str, float]) -> float: ...


def corner_delivery_space() -> SearchSpace:
    """The v1 delivery sub-space (bounds match Routine Spec validation)."""
    return SearchSpace(
        params=(
            ContinuousParam("target_x", 40.0, 52.0),
            ContinuousParam("target_y", -8.0, 8.0),
            ContinuousParam("speed_ms", 16.0, 32.0),
            ContinuousParam("spin_rps", 2.0, 12.0),
        )
    )


class RoutineObjective:
    """Concrete ObjectiveFunction: mutate delivery params -> compile -> Monte
    Carlo -> P(goal). Deterministic per (params, root_seed): supports common
    random numbers across optimizer trials (M-3)."""

    def __init__(
        self,
        base_scenario: Scenario,
        space: SearchSpace,
        n_sims: int = 200,
        root_seed: int = 0,
        runner: MonteCarloRunner | None = None,
    ) -> None:
        self._base = base_scenario
        self._space = space
        self._n = n_sims
        self._seed = root_seed
        self._runner = runner if runner is not None else MonteCarloRunner()

    def evaluate(self, values: Mapping[str, float]) -> EvaluationResult:
        v = self._space.validate(values)
        delivery = self._base.routine.delivery
        new_delivery = Delivery(
            type=delivery.type,
            target=PitchPoint(
                x=v.get("target_x", delivery.target.x),
                y=v.get("target_y", delivery.target.y),
            ),
            speed_ms=v.get("speed_ms", delivery.speed_ms),
            spin_rps=v.get("spin_rps", delivery.spin_rps),
        )
        routine = self._base.routine.model_copy(update={"delivery": new_delivery})
        scenario = self._base.model_copy(update={"routine": routine})
        program = compile_scenario(scenario)
        batch = self._runner.run(program, self._n, self._seed)
        stats = aggregate(batch)
        return EvaluationResult(objective=stats.p_goal.p, n_sims=self._n, root_seed=self._seed)

    def __call__(self, values: Mapping[str, float]) -> float:
        return self.evaluate(values).objective

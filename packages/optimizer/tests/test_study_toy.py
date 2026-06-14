"""Optimizer driver on a known toy landscape (doc 06 sec4): TPE recovers a
planted optimum and beats random search at equal budget; random beats nothing.

Engine-free: the objective is a closed-form Gaussian peak, so this test is fast
and isolates the search algorithm from simulator noise."""

import math
from collections.abc import Mapping

from restart.optimize.genome import ContinuousParam, SearchSpace
from restart_opt.study import run_study

SPACE = SearchSpace((ContinuousParam("x", 0.0, 10.0), ContinuousParam("y", 0.0, 10.0)))
_X0, _Y0 = 7.0, 3.0


def peak(params: Mapping[str, object]) -> float:
    x = float(params["x"])  # type: ignore[arg-type]
    y = float(params["y"])  # type: ignore[arg-type]
    return math.exp(-((x - _X0) ** 2 + (y - _Y0) ** 2))


# A 6-D landscape: random search degrades with dimensionality while TPE
# concentrates sampling, so the sample-efficiency advantage is robust here
# (on a smooth 2-D peak random search is a strong baseline -- doc 06 sec3.2).
_SPACE6 = SearchSpace(tuple(ContinuousParam(f"d{i}", 0.0, 10.0) for i in range(6)))
_OPT6 = (7.0, 3.0, 2.0, 8.0, 5.0, 1.0)


def peak6(params: Mapping[str, object]) -> float:
    sq = sum((float(params[f"d{i}"]) - c) ** 2 for i, c in enumerate(_OPT6))  # type: ignore[arg-type]
    return math.exp(-0.2 * sq)


class TestRunStudy:
    def test_deterministic_same_seed(self) -> None:
        a = run_study(peak, SPACE, n_trials=25, sampler="tpe", seed=1)
        b = run_study(peak, SPACE, n_trials=25, sampler="tpe", seed=1)
        assert a.best_params == b.best_params
        assert a.best_value == b.best_value

    def test_tpe_recovers_planted_optimum(self) -> None:
        out = run_study(peak, SPACE, n_trials=60, sampler="tpe", seed=1)
        assert out.best_value > 0.7
        assert abs(float(out.best_params["x"]) - _X0) < 1.5
        assert abs(float(out.best_params["y"]) - _Y0) < 1.5

    def test_tpe_beats_random_at_equal_budget(self) -> None:
        tpe = run_study(peak6, _SPACE6, n_trials=80, sampler="tpe", seed=1)
        rnd = run_study(peak6, _SPACE6, n_trials=80, sampler="random", seed=1)
        assert tpe.best_value > rnd.best_value

    def test_random_beats_nothing(self) -> None:
        rnd = run_study(peak, SPACE, n_trials=40, sampler="random", seed=2)
        # Found real signal, far better than an arbitrary corner of the space.
        assert rnd.best_value > peak({"x": 0.0, "y": 10.0})
        assert rnd.best_value > 0.01

    def test_records_all_trials(self) -> None:
        out = run_study(peak, SPACE, n_trials=10, sampler="tpe", seed=3)
        assert len(out.trials) == 10
        assert out.sampler == "tpe"
        assert all(t.value is not None for t in out.trials)


def test_infeasible_objective_is_pruned_not_crashed() -> None:
    def picky(params: Mapping[str, object]) -> float:
        x = float(params["x"])  # type: ignore[arg-type]
        if x > 5.0:
            raise ValueError("infeasible region")
        return x

    out = run_study(picky, SPACE, n_trials=20, sampler="random", seed=4)
    # Study completes; best stays in the feasible region.
    assert float(out.best_params["x"]) <= 5.0

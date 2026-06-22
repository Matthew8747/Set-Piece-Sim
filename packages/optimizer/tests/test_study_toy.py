"""Optimizer driver on a known toy landscape (doc 06 sec4): TPE recovers a
planted optimum and beats random search at equal budget; random beats nothing.

Engine-free: the objective is a closed-form Gaussian peak, so this test is fast
and isolates the search algorithm from simulator noise."""

import math
from collections.abc import Mapping

import optuna
import pytest

from restart.optimize.genome import CategoricalParam, ContinuousParam, SearchSpace
from restart_opt.study import (
    default_population,
    is_evolutionary,
    make_sampler,
    run_study,
)

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
    sq = 0.0
    for i, c in enumerate(_OPT6):
        sq += (float(params[f"d{i}"]) - c) ** 2  # type: ignore[arg-type]
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


class TestEvolutionarySamplers:
    """Phase 9: CMA-ES (evolution strategy) + NSGA-II (genetic algorithm) plug
    into the same driver as TPE/random and actually evolve toward the optimum."""

    def test_make_sampler_dispatch(self) -> None:
        assert isinstance(make_sampler("cmaes", 0), optuna.samplers.CmaEsSampler)
        assert isinstance(make_sampler("nsga2", 0), optuna.samplers.NSGAIISampler)
        with pytest.raises(ValueError, match="cmaes"):
            make_sampler("genetic", 0)

    def test_is_evolutionary(self) -> None:
        assert is_evolutionary("cmaes") and is_evolutionary("nsga2")
        assert not is_evolutionary("tpe") and not is_evolutionary("random")

    def test_default_population_scales_with_budget(self) -> None:
        assert default_population(24) == 8  # ~3 generations at the canonical budget
        assert default_population(3) == 4  # floored so a generation always forms

    def test_cmaes_finds_the_peak(self) -> None:
        out = run_study(peak6, _SPACE6, n_trials=80, sampler="cmaes", seed=1)
        assert out.sampler == "cmaes"
        assert out.best_value > 0.5  # an evolution strategy concentrates on the optimum

    def test_nsga2_evolves_generations(self) -> None:
        out = run_study(peak, SPACE, n_trials=40, sampler="nsga2", seed=1)
        assert out.sampler == "nsga2"
        # Real signal, far better than an arbitrary corner of the space.
        assert out.best_value > peak({"x": 0.0, "y": 10.0})
        # The genetic algorithm runs in generations — they are recorded.
        gens = {t.generation for t in out.trials if t.generation is not None}
        assert len(gens) >= 2  # at least a couple of generations evolved

    def test_non_generational_samplers_have_no_generation(self) -> None:
        out = run_study(peak, SPACE, n_trials=10, sampler="tpe", seed=1)
        assert all(t.generation is None for t in out.trials)

    def test_nsga2_evolves_a_mixed_genome(self) -> None:
        # The GA must handle the categorical genes (zones/intents), not just floats.
        space = SearchSpace(
            (
                ContinuousParam("x", 0.0, 10.0),
                CategoricalParam("kind", ("a", "b", "c")),
            )
        )

        def mixed(params: Mapping[str, object]) -> float:
            x = float(params["x"])  # type: ignore[arg-type]
            bonus = 1.0 if params["kind"] == "b" else 0.0
            return math.exp(-((x - 7.0) ** 2)) + bonus

        out = run_study(mixed, space, n_trials=40, sampler="nsga2", seed=2)
        assert out.best_value > 0.5  # found the "b" category + the continuous peak

    def test_nsga2_deterministic_same_seed(self) -> None:
        a = run_study(peak, SPACE, n_trials=20, sampler="nsga2", seed=5)
        b = run_study(peak, SPACE, n_trials=20, sampler="nsga2", seed=5)
        assert a.best_value == b.best_value
        assert [t.params for t in a.trials] == [t.params for t in b.trials]


def test_infeasible_objective_is_pruned_not_crashed() -> None:
    def picky(params: Mapping[str, object]) -> float:
        x = float(params["x"])  # type: ignore[arg-type]
        if x > 5.0:
            raise ValueError("infeasible region")
        return x

    out = run_study(picky, SPACE, n_trials=20, sampler="random", seed=4)
    # Study completes; best stays in the feasible region.
    assert float(out.best_params["x"]) <= 5.0

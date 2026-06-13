"""Monte Carlo layer tests: determinism, statistics, report shape, and the
optimization interface contract."""

import time

import pytest

from restart.montecarlo import MonteCarloRunner, aggregate, build_report
from restart.montecarlo.aggregate import wilson
from restart.montecarlo.runner import sim_seeds
from restart.optimize import ObjectiveFunction, RoutineObjective, corner_delivery_space
from restart.players.demo import demo_team
from restart.players.player import PositionGroup
from restart.tactics.compile import Scenario, SimProgram, compile_scenario
from restart.tactics.library import all_corner_routines, all_schemes

ATT = demo_team("ENG", "England", 1)
DEF = demo_team("ARG", "Argentina", 2)


def make_scenario() -> Scenario:
    routine = all_corner_routines()[0]
    kicker = max(ATT.players, key=lambda p: p.attributes.delivery).player_id
    outfield = [
        p.player_id
        for p in ATT.players
        if p.position_group is not PositionGroup.GK and p.player_id != kicker
    ]
    roles = {a.role: outfield[i] for i, a in enumerate(routine.assignments)}
    return Scenario(
        routine=routine,
        attacking_team=ATT,
        defending_team=DEF,
        kicker_id=kicker,
        role_assignments=roles,
        scheme=all_schemes()[0],
    )


PROGRAM: SimProgram = compile_scenario(make_scenario())
RUNNER = MonteCarloRunner()


class TestSeeds:
    def test_per_sim_seeds_stable_across_batch_sizes(self) -> None:
        """Sim i's seed is independent of n: any sim is replayable singly."""
        assert sim_seeds(7, 10) == sim_seeds(7, 50)[:10]

    def test_different_roots_differ(self) -> None:
        assert sim_seeds(1, 5) != sim_seeds(2, 5)

    def test_invalid_inputs(self) -> None:
        with pytest.raises(ValueError, match="root_seed"):
            sim_seeds(-1, 5)
        with pytest.raises(ValueError, match="n_sims"):
            RUNNER.run(PROGRAM, 0)


class TestBatchDeterminism:
    def test_same_root_seed_identical_outcomes(self) -> None:
        a = RUNNER.run(PROGRAM, 12, root_seed=3)
        b = RUNNER.run(PROGRAM, 12, root_seed=3)
        assert [r.outcome for r in a.results] == [r.outcome for r in b.results]

    def test_progress_callback_fires(self) -> None:
        calls: list[tuple[int, int]] = []
        RUNNER.run(PROGRAM, 60, root_seed=1, on_progress=lambda d, t: calls.append((d, t)))
        assert calls == [(50, 60)]


class TestAggregation:
    def test_wilson_interval_brackets_p(self) -> None:
        ci = wilson(3, 100)
        assert 0.0 <= ci.lo < ci.p < ci.hi <= 1.0
        assert ci.k == 3 and ci.n == 100

    def test_wilson_empty_batch_degenerate(self) -> None:
        ci = wilson(0, 0)
        assert (ci.lo, ci.hi) == (0.0, 1.0)

    def test_stats_consistent(self) -> None:
        batch = RUNNER.run(PROGRAM, 60, root_seed=5)
        stats = aggregate(batch)
        assert stats.n_sims == 60
        assert sum(stats.outcome_counts.values()) == 60
        # goals <= shots (every goal requires a shot)
        assert stats.p_goal.k <= stats.p_shot.k
        # headers are a subset of shots
        assert stats.p_header_shot.k <= stats.p_shot.k

    def test_report_serializes(self) -> None:
        report = build_report(RUNNER.run(PROGRAM, 20, root_seed=2))
        d = report.to_dict()
        assert d["engine_version"].startswith("sim/")
        assert d["n_sims"] == 20
        assert set(d["p_goal"]) == {"p", "lo", "hi", "k", "n"}


class TestOptimizationInterface:
    def test_routine_objective_satisfies_protocol(self) -> None:
        obj = RoutineObjective(make_scenario(), corner_delivery_space(), n_sims=10)
        assert isinstance(obj, ObjectiveFunction)

    def test_objective_deterministic_and_bounded(self) -> None:
        obj = RoutineObjective(make_scenario(), corner_delivery_space(), n_sims=15, root_seed=4)
        params = {"target_x": 48.0, "target_y": -2.0, "speed_ms": 24.0, "spin_rps": 8.0}
        a, b = obj(params), obj(params)
        assert a == b
        assert 0.0 <= a <= 1.0

    def test_out_of_bounds_rejected(self) -> None:
        obj = RoutineObjective(make_scenario(), corner_delivery_space(), n_sims=5)
        with pytest.raises(ValueError, match="outside"):
            obj({"target_x": 60.0})

    def test_unknown_param_rejected(self) -> None:
        obj = RoutineObjective(make_scenario(), corner_delivery_space(), n_sims=5)
        with pytest.raises(ValueError, match="unknown"):
            obj({"nonsense": 1.0})


class TestThroughputRecord:
    def test_100_sims_timing(self) -> None:
        """Records reference-engine MC throughput; generous CI gate. The fused
        batch kernel (ADR-003 d8) is the real 100k answer — this documents the
        baseline it must beat."""
        start = time.perf_counter()
        RUNNER.run(PROGRAM, 100, root_seed=9)
        elapsed = time.perf_counter() - start
        print(f"\nMC 100 sims: {elapsed:.2f}s ({100 / elapsed:.0f} sims/s)")
        assert elapsed < 60.0

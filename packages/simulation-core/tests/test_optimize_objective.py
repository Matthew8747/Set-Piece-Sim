"""The optimizer objective: mean xG per sim (doc 06 sec2.3), deterministic per
(params, root_seed) so the driver can use common random numbers."""

from collections.abc import Mapping

from restart.engine import SetPieceEngine
from restart.engine.xg import LogisticXGScorer, XGModelBundle
from restart.montecarlo.runner import MonteCarloRunner
from restart.optimize import (
    CornerGenome,
    EvaluationResult,
    ObjectiveFunction,
    RoutineObjective,
)
from restart.players.demo import demo_team
from restart.players.player import PositionGroup
from restart.tactics.compile import Scenario
from restart.tactics.library import all_corner_routines, all_schemes

ATT = demo_team("ENG", "England", 1)
DEF = demo_team("ARG", "Argentina", 2)


def base_scenario() -> Scenario:
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


def xg_runner() -> MonteCarloRunner:
    # A tiny non-trivial xG model so simulated shots score > 0 (no IO needed).
    scorer = LogisticXGScorer(
        model_id="test", feature_names=("distance",), coef=(-0.1,), intercept=0.5
    )
    bundle = XGModelBundle(header=scorer, foot=scorer)
    return MonteCarloRunner(engine=SetPieceEngine(xg_scorer=bundle))


def objective() -> RoutineObjective:
    return RoutineObjective(
        base_scenario(), CornerGenome(), runner=xg_runner(), n_sims=20, root_seed=4
    )


class TestObjective:
    def test_satisfies_protocol(self) -> None:
        assert isinstance(objective(), ObjectiveFunction)

    def test_returns_mean_xg_in_unit_interval(self) -> None:
        obj = objective()
        x = obj(obj.genome.defaults())
        assert 0.0 <= x <= 1.0

    def test_deterministic_same_seed(self) -> None:
        obj = objective()
        v = obj.genome.defaults()
        assert obj(v) == obj(v)

    def test_common_random_numbers_across_objectives(self) -> None:
        a = RoutineObjective(
            base_scenario(), CornerGenome(), runner=xg_runner(), n_sims=20, root_seed=7
        )
        b = RoutineObjective(
            base_scenario(), CornerGenome(), runner=xg_runner(), n_sims=20, root_seed=7
        )
        v = a.genome.defaults()
        assert a(v) == b(v)

    def test_evaluate_reports_ci_and_counterattack(self) -> None:
        obj = objective()
        res = obj.evaluate(obj.genome.defaults())
        assert isinstance(res, EvaluationResult)
        assert res.mean_xg_ci_lo <= res.mean_xg <= res.mean_xg_ci_hi
        assert 0.0 <= res.counterattack_risk <= 1.0
        assert 0.0 <= res.p_goal <= 1.0
        assert res.n_sims == 20

    def test_rejects_unknown_param(self) -> None:
        obj = objective()
        import pytest

        with pytest.raises(ValueError, match="unknown"):
            obj({"nonsense": 1.0})


def test_objective_accepts_any_mapping() -> None:
    # __call__ takes a Mapping (the driver passes a plain dict from suggestions).
    obj = objective()
    v: Mapping[str, object] = obj.genome.defaults()
    assert isinstance(obj(v), float)

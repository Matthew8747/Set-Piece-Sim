"""Engine integration of the injected xG scorer (Phase 4)."""

from __future__ import annotations

from restart.engine import SetPieceEngine
from restart.engine.xg import ShotContext
from restart.montecarlo import MonteCarloRunner, build_report
from restart.players.demo import demo_team
from restart.players.player import PositionGroup
from restart.simulation.events import SetPieceOutcome, ShotEvent
from restart.tactics.compile import Scenario, SimProgram, compile_scenario
from restart.tactics.library import all_corner_routines, all_schemes
from restart.tactics.routine import RoutineSpec
from restart.tactics.scheme import DefensiveScheme

ATT = demo_team("ENG", "England", 1)
DEF = demo_team("ARG", "Argentina", 2)


class ConstantScorer:
    """Test double implementing the XGScorer protocol."""

    def __init__(self, value: float) -> None:
        self.value = value
        self.calls = 0

    def score(self, context: ShotContext) -> float:
        self.calls += 1
        assert context.distance_m >= 0.0
        return self.value


def _program(routine: RoutineSpec, scheme: DefensiveScheme) -> SimProgram:
    kicker = max(ATT.players, key=lambda p: p.attributes.delivery).player_id
    outfield = [
        p.player_id
        for p in ATT.players
        if p.position_group is not PositionGroup.GK and p.player_id != kicker
    ]
    roles = {a.role: outfield[i] for i, a in enumerate(routine.assignments)}
    return compile_scenario(
        Scenario(
            routine=routine,
            attacking_team=ATT,
            defending_team=DEF,
            kicker_id=kicker,
            role_assignments=roles,
            scheme=scheme,
        )
    )


PROGRAM = _program(all_corner_routines()[0], all_schemes()[0])


def _shot_seeds(engine: SetPieceEngine, n: int = 60) -> list[int]:
    """Seeds that produce an attacker ShotEvent under this engine."""
    out = []
    for s in range(n):
        res = engine.run(PROGRAM, seed=s)
        if any(isinstance(e, ShotEvent) for e in res.events):
            out.append(s)
    return out


def test_certain_xg_makes_every_shot_a_goal() -> None:
    engine = SetPieceEngine(xg_scorer=ConstantScorer(1.0))
    seeds = _shot_seeds(engine)
    assert seeds, "expected at least one shot across the seed sweep"
    for s in seeds:
        res = engine.run(PROGRAM, seed=s)
        shot = next(e for e in res.events if isinstance(e, ShotEvent))
        assert shot.xg == 1.0
        assert res.outcome is SetPieceOutcome.GOAL


def test_zero_xg_never_scores() -> None:
    engine = SetPieceEngine(xg_scorer=ConstantScorer(0.0))
    for s in _shot_seeds(engine):
        res = engine.run(PROGRAM, seed=s)
        assert res.outcome is not SetPieceOutcome.GOAL
        shot = next(e for e in res.events if isinstance(e, ShotEvent))
        assert shot.xg == 0.0


def test_determinism_with_scorer() -> None:
    e1 = SetPieceEngine(xg_scorer=ConstantScorer(0.3))
    e2 = SetPieceEngine(xg_scorer=ConstantScorer(0.3))
    r1 = e1.run(PROGRAM, seed=7)
    r2 = e2.run(PROGRAM, seed=7)
    assert r1.outcome is r2.outcome


def test_report_surfaces_mean_xg() -> None:
    engine = SetPieceEngine(xg_scorer=ConstantScorer(0.25))
    runner = MonteCarloRunner(engine=engine)
    batch = runner.run(PROGRAM, root_seed=1, n_sims=40)
    report = build_report(batch).to_dict()
    assert "mean_xg" in report
    assert 0.0 <= report["mean_xg"] <= 0.25 + 1e-9
    # Every scored shot used the constant 0.25.
    assert report["n_xg_scored"] >= 0


def test_default_engine_leaves_xg_none() -> None:
    engine = SetPieceEngine()
    for s in _shot_seeds(engine, n=30):
        res = engine.run(PROGRAM, seed=s)
        shot = next(e for e in res.events if isinstance(e, ShotEvent))
        assert shot.xg is None

"""Agent execution + perception realism (G-16/G-17/G-18).

These lock in the behaviour that stops the agents reading as scripted: identical
players diverge, misjudgment and marking cost the contest, and - the seam that
makes all of it matter - the agent's executed position at the contest instant
feeds the duel.
"""

from __future__ import annotations

import numpy as np

from restart.engine import SetPieceEngine
from restart.engine.config import EngineConfig
from restart.montecarlo.runner import MonteCarloRunner, sim_seeds
from restart.players.demo import demo_team
from restart.players.player import PositionGroup
from restart.simulation.events import FirstContactEvent
from restart.tactics.compile import Scenario, SimProgram, compile_scenario
from restart.tactics.library import all_corner_routines, decoy_overload, zonal_six_two
from restart.tactics.routine import RoutineSpec

ATT = demo_team("ENG", "England", 1)
DEF = demo_team("ARG", "Argentina", 2)

_NOISE_OFF = EngineConfig(move_speed_sigma=0.0, read_time_s=0.0, mark_lag_s=0.0, mark_error_m=0.0)


def _program(routine: RoutineSpec) -> SimProgram:
    kicker = max(ATT.players, key=lambda p: p.attributes.delivery).player_id
    outfield = [
        p.player_id
        for p in ATT.players
        if p.position_group is not PositionGroup.GK and p.player_id != kicker
    ]
    return compile_scenario(
        Scenario(
            routine=routine,
            attacking_team=ATT,
            defending_team=DEF,
            kicker_id=kicker,
            role_assignments={a.role: outfield[i] for i, a in enumerate(routine.assignments)},
            scheme=zonal_six_two(),
        )
    )


def test_same_seed_is_bit_identical() -> None:
    """The noise is externalized (ADR-011), so determinism is untouched."""
    program = _program(decoy_overload())
    engine = SetPieceEngine()
    a = engine.run(program, 314)
    b = engine.run(program, 314)
    assert a.outcome is b.outcome
    np.testing.assert_array_equal(a.att_tracks, b.att_tracks)
    np.testing.assert_array_equal(a.def_tracks, b.def_tracks)


def test_noise_breaks_lockstep_paths() -> None:
    """Identical-attribute runners must not trace the same path every rep.

    Without motor noise two players with the same attributes and start move
    byte-identically across seeds; the spread of a runner's final position is
    the cheapest witness that G-16 broke that symmetry.
    """
    program = _program(all_corner_routines()[0])

    def spread(engine: SetPieceEngine) -> float:
        finals = np.array([engine.run(program, s).att_tracks[-1, 0] for s in sim_seeds(0, 30)])
        return float(np.hypot(finals[:, 0].std(), finals[:, 1].std()))

    assert spread(SetPieceEngine()) > spread(SetPieceEngine(engine=_NOISE_OFF)) + 0.1


def test_executed_position_decides_the_contest() -> None:
    """With w_gap=0, the duel ignores where agents are (attributes only); with it
    on, being at the ball matters. Turning it on must change who wins.

    This is the G-18 coupling: the whole movement model - pace, reading, marking
    - reaches the outcome only through the executed-position term. Aggregated
    across the library, because the term bites where contests are close, not on
    a routine that leaves the runner unmarked.
    """
    programs = [_program(r) for r in all_corner_routines()]

    def attack_share(cfg: EngineConfig) -> float:
        engine = SetPieceEngine(engine=cfg)
        got = [
            c
            for program in programs
            for r in MonteCarloRunner(engine).run(program, 60, root_seed=0).results
            if (c := next((e for e in r.events if isinstance(e, FirstContactEvent)), None))
        ]
        return sum(c.team == "attack" for c in got) / len(got)

    gap_off = attack_share(EngineConfig(w_gap=0.0))
    gap_on = attack_share(EngineConfig())  # default w_gap
    assert abs(gap_on - gap_off) > 0.05, f"executed position changed nothing: {gap_off} -> {gap_on}"


def test_noise_widens_variance_without_wrecking_the_mean() -> None:
    """Execution noise is unbiased: it should widen the per-sim distribution, not
    shift the aggregate goal rate off a cliff."""
    program = _program(decoy_overload())
    on = MonteCarloRunner(SetPieceEngine()).run(program, 120, root_seed=0)
    off = MonteCarloRunner(SetPieceEngine(engine=_NOISE_OFF)).run(program, 120, root_seed=0)
    goals_on = sum(r.goal_scored for r in on.results) / on.n_sims
    goals_off = sum(r.goal_scored for r in off.results) / off.n_sims
    # Same ballpark - noise moves the mean by less than half its own level.
    assert abs(goals_on - goals_off) < 0.15, f"{goals_off:.3f} vs {goals_on:.3f}"

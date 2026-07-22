"""Delivery-aim regression tests.

These lock in the Phase-11 aim fix. Before it, the engine aimed with the
drag-free range equation plus a fixed carry fudge factor, and every stock corner
missed: deliveries landed 3.3-6.8 m from their nominal target and 19-99% of them
went out of play, which flattened the differences between routines into noise.

Each test below fails against that old behaviour.
"""

import math
from collections import Counter

import numpy as np
import pytest

from restart.engine import SetPieceEngine
from restart.engine.aim import solve_aim
from restart.engine.config import EngineConfig
from restart.montecarlo.runner import MonteCarloRunner
from restart.physics.config import PhysicsConfig
from restart.players.demo import demo_team
from restart.players.player import PositionGroup
from restart.simulation.events import SetPieceOutcome
from restart.tactics.compile import Scenario, SimProgram, compile_scenario
from restart.tactics.library import all_corner_routines, zonal_six_two
from restart.tactics.routine import RoutineSpec

ATT = demo_team("ENG", "England", 1)
DEF = demo_team("ARG", "Argentina", 2)

KICK_X, KICK_Y = 52.2, -33.7


def _program(routine: RoutineSpec) -> SimProgram:
    """Compile a routine the way the API does: best deliverer takes the corner."""
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


@pytest.mark.parametrize("routine", all_corner_routines(), ids=lambda r: r.name)
def test_solved_launch_lands_on_target(routine: RoutineSpec) -> None:
    """The solved launch puts the ball on the routine's delivery target.

    This is the property the old range-equation heuristic did not have: it was
    wrong by 3.3-6.8 m on the stock library.
    """
    cfg, phys = EngineConfig(), PhysicsConfig.default()
    target = (routine.delivery.target.x, routine.delivery.target.y)
    spin = {"inswinger": -1.0, "outswinger": 1.0}.get(routine.delivery.type.value, 0.0)
    rps = {"driven": 2.0, "floated": 1.0, "short": 0.0}.get(
        routine.delivery.type.value, routine.delivery.spin_rps
    )

    speed, elev, heading = solve_aim(
        KICK_X,
        KICK_Y,
        target[0],
        target[1],
        routine.delivery.speed_ms,
        spin * rps,
        cfg.elev_min_deg,
        cfg.elev_max_deg,
        cfg.max_delivery_speed_ms,
        cfg.aim_tolerance_m,
        phys,
    )

    from restart.physics.batch import simulate_flights

    y0 = np.zeros((1, 9))
    y0[0, 0], y0[0, 1], y0[0, 2] = KICK_X, KICK_Y, 0.11
    y0[0, 3] = speed * math.cos(elev) * math.cos(heading)
    y0[0, 4] = speed * math.cos(elev) * math.sin(heading)
    y0[0, 5] = speed * math.sin(elev)
    y0[0, 8] = spin * rps * 2.0 * math.pi
    res = simulate_flights(y0, phys)

    assert bool(res.landed[0]), "solved delivery never lands"
    landing = res.landing_position[0]
    miss = math.hypot(landing[0] - target[0], landing[1] - target[1])
    assert miss < 1.5, f"{routine.name}: lands {miss:.2f} m from target"


def test_solve_aim_is_deterministic() -> None:
    """Same inputs, same launch - the solve must not drift between calls."""
    cfg, phys = EngineConfig(), PhysicsConfig.default()
    args = (
        KICK_X,
        KICK_Y,
        49.5,
        -2.5,
        24.0,
        -8.0,
        cfg.elev_min_deg,
        cfg.elev_max_deg,
        cfg.max_delivery_speed_ms,
        cfg.aim_tolerance_m,
        phys,
    )
    solve_aim.cache_clear()
    first = solve_aim(*args)
    solve_aim.cache_clear()
    second = solve_aim(*args)
    assert first == second


def test_solver_never_aims_out_of_play() -> None:
    """An outswinger target it cannot legally reach must not be 'reached' by
    firing the ball over the goal line.

    The unbounded solver did exactly that for the old (50.5, 5.0) far-post
    outswinger target - it picked a heading 0.3 m from the corner flag pointing
    across the goal line, because the landing point beyond the line still scored
    well. The chosen heading must keep the ball on the field.
    """
    cfg, phys = EngineConfig(), PhysicsConfig.default()
    speed, elev, heading = solve_aim(
        KICK_X,
        KICK_Y,
        50.5,
        5.0,
        23.0,
        7.0,
        cfg.elev_min_deg,
        cfg.elev_max_deg,
        cfg.max_delivery_speed_ms,
        cfg.aim_tolerance_m,
        phys,
    )
    # Fly it and check the whole path, not a straight-line extrapolation: an
    # outswinger legitimately starts out toward the goal line and is bent back,
    # so only the integrated trajectory can answer this.
    from restart.physics.batch import simulate_flights

    y0 = np.zeros((1, 9))
    y0[0, 0], y0[0, 1], y0[0, 2] = KICK_X, KICK_Y, 0.11
    y0[0, 3] = speed * math.cos(elev) * math.cos(heading)
    y0[0, 4] = speed * math.cos(elev) * math.sin(heading)
    y0[0, 5] = speed * math.sin(elev)
    y0[0, 8] = 7.0 * 2.0 * math.pi
    res = simulate_flights(y0, phys)
    assert bool(res.landed[0])
    landing = res.landing_position[0]
    assert abs(landing[0]) <= 52.5, f"delivery lands off the goal line at x={landing[0]:.2f}"
    assert abs(landing[1]) <= 34.0, f"delivery lands off the touchline at y={landing[1]:.2f}"


@pytest.mark.parametrize("routine", all_corner_routines(), ids=lambda r: r.name)
def test_deliveries_stay_in_play(routine: RoutineSpec) -> None:
    """A stock routine must not spray the ball out of play.

    Measured before the fix: 34% / 31% / 65% / 99% / 19% out of play across the
    five corner routines. A delivery that leaves the field cannot be simulated
    into a chance, so this was the direct cause of routines not diverging.
    """
    batch = MonteCarloRunner(SetPieceEngine()).run(_program(routine), 60, root_seed=0)
    outcomes = Counter(r.outcome for r in batch.results)
    out_rate = outcomes[SetPieceOutcome.OUT_OF_PLAY] / batch.n_sims
    assert out_rate <= 0.15, f"{routine.name}: {out_rate:.0%} out of play - {dict(outcomes)}"


def test_short_corner_is_received_not_shot() -> None:
    """The short-corner receiver keeps the ball; they do not shoot from 28 m wide.

    Two bugs met here. The receiver's SHORT_OPTION intent was excluded from the
    first-contact contest, so nobody could ever touch a short corner (99/100 out
    of play). Admitting them to the contest then routed them into the shot model,
    which produced 77% off-target efforts from out by the touchline.
    """
    routine = next(r for r in all_corner_routines() if r.name == "edge_of_box_pullback")
    batch = MonteCarloRunner(SetPieceEngine()).run(_program(routine), 40, root_seed=0)
    outcomes = Counter(r.outcome for r in batch.results)

    assert outcomes[SetPieceOutcome.OUT_OF_PLAY] == 0
    assert outcomes[SetPieceOutcome.OFF_TARGET] == 0
    assert outcomes[SetPieceOutcome.SECOND_BALL_ATTACK] >= 30


def test_routines_produce_distinct_outcome_profiles() -> None:
    """Different routines must actually simulate differently.

    The user-visible symptom of the aiming bug was that every routine collapsed
    to the same behaviour. Distinct goal rates are the cheapest check that the
    content library is doing work.
    """
    runner = MonteCarloRunner(SetPieceEngine())
    goal_rates = {}
    for routine in all_corner_routines():
        batch = runner.run(_program(routine), 60, root_seed=0)
        goals = sum(1 for r in batch.results if r.outcome is SetPieceOutcome.GOAL)
        goal_rates[routine.name] = goals / batch.n_sims

    assert len(set(goal_rates.values())) > 1, f"all routines identical: {goal_rates}"
    assert max(goal_rates.values()) - min(goal_rates.values()) > 0.03, goal_rates

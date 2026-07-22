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

from restart.domain import pitch
from restart.engine import SetPieceEngine
from restart.engine.aim import solve_aim
from restart.engine.config import EngineConfig
from restart.montecarlo.runner import MonteCarloRunner
from restart.physics import _kernels
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


def _arrival_xy(
    routine: RoutineSpec, speed: float, elev: float, heading: float, contact_height_m: float
) -> tuple[float, float] | None:
    """Where the solved launch descends through heading height, by integration."""
    spin, rps = _spin_of(routine)
    y0 = np.zeros((1, 9))
    y0[0, 0], y0[0, 1], y0[0, 2] = KICK_X, KICK_Y, 0.11
    y0[0, 3] = speed * math.cos(elev) * math.cos(heading)
    y0[0, 4] = speed * math.cos(elev) * math.sin(heading)
    y0[0, 5] = speed * math.sin(elev)
    y0[0, 8] = spin * rps * 2.0 * math.pi

    phys = PhysicsConfig.default()
    ball, env = phys.ball, phys.environment
    xy, ok = _kernels.aim_probe(
        np.ascontiguousarray(y0),
        phys.integrator.dt_s,
        1200,
        ball.radius_m,
        pitch.HALF_LENGTH_M,
        pitch.HALF_WIDTH_M,
        contact_height_m,
        env.gravity_ms2,
        0.5 * env.air_density_kgm3 * ball.cross_section_m2 / ball.mass_kg,
        ball.drag.cd_subcritical,
        ball.drag.cd_supercritical,
        ball.drag.v_critical_ms,
        ball.drag.transition_width_ms,
        ball.radius_m,
        ball.magnus.coeff_a,
        ball.magnus.coeff_b,
        ball.magnus.spin_parameter_max,
        ball.spin_decay_tau_s,
    )
    return (float(xy[0, 0]), float(xy[0, 1])) if bool(ok[0]) else None


def _spin_of(routine: RoutineSpec) -> tuple[float, float]:
    sign = {"inswinger": -1.0, "outswinger": 1.0}.get(routine.delivery.type.value, 0.0)
    rps = {"driven": 2.0, "floated": 1.0, "short": 0.0}.get(
        routine.delivery.type.value, routine.delivery.spin_rps
    )
    return sign, rps


@pytest.mark.parametrize("routine", all_corner_routines(), ids=lambda r: r.name)
def test_solved_launch_arrives_on_target(routine: RoutineSpec) -> None:
    """The solved launch puts the ball on target *at heading height*.

    Two properties the old range-equation heuristic lacked: it was wrong by
    3.3-6.8 m, and it aimed the landing point, which drops the ball into contest
    range ~5 m short of the runner's mark.
    """
    cfg = EngineConfig()
    target = (routine.delivery.target.x, routine.delivery.target.y)
    sign, rps = _spin_of(routine)

    speed, elev, heading = solve_aim(
        KICK_X,
        KICK_Y,
        target[0],
        target[1],
        routine.delivery.speed_ms,
        sign * rps,
        cfg.elev_min_deg,
        cfg.elev_max_deg,
        cfg.max_delivery_speed_ms,
        cfg.aim_tolerance_m,
        cfg.contact_height_m,
        PhysicsConfig.default(),
    )

    arrival = _arrival_xy(routine, speed, elev, heading, cfg.contact_height_m)
    assert arrival is not None, f"{routine.name}: solved delivery never arrives in play"
    miss = math.hypot(arrival[0] - target[0], arrival[1] - target[1])
    assert miss < 1.5, f"{routine.name}: arrives {miss:.2f} m from target"


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
        cfg.contact_height_m,
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
        cfg.contact_height_m,
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


def test_contesting_attackers_go_to_the_ball() -> None:
    """ATTACK_BALL runners must attack the delivery, not run out their script.

    The contest used to be resolved from an interception plan nobody executed:
    agents ticked toward their scripted RunLeg target while the contest maths
    assumed they had chased the ball. Measured, the nearest ATTACK_BALL runner
    stood 6.05 m from the ball at the contest instant on the near-post
    inswinger - it went past them.
    """
    from restart.simulation.events import FirstContactEvent
    from restart.tactics.routine import INTENT_CODES, Intent

    attack_ball = INTENT_CODES[Intent.ATTACK_BALL]
    routine = next(r for r in all_corner_routines() if r.name == "near_post_inswinger")
    program = _program(routine)
    engine = SetPieceEngine()

    gaps = []
    for result in MonteCarloRunner(engine).run(program, 40, root_seed=0).results:
        contact = next((e for e in result.events if isinstance(e, FirstContactEvent)), None)
        if contact is None:
            continue
        k = min(
            int(np.searchsorted(result.track_times_s, contact.time_s)),
            len(result.track_times_s) - 1,
        )
        runners = [
            i for i in range(program.n_attackers) if int(program.att_intent[i]) == attack_ball
        ]
        ball_xy = np.asarray(contact.position[:2])
        gaps.append(min(float(np.linalg.norm(result.att_tracks[k, i] - ball_xy)) for i in runners))

    assert gaps, "no first contact in any sim"
    assert float(np.mean(gaps)) < 4.0, f"runners average {np.mean(gaps):.2f} m from the ball"


def test_zonal_defenders_do_not_all_charge_the_ball() -> None:
    """Defenders only leave their post for a ball that comes near it (G-15).

    The contest is a Gumbel-max, so it is decided partly by headcount. Letting
    every outfielder contest made the attack structurally unable to win a
    delivery: attackers took 2-15% of first contacts. A zonal defender holding a
    zone 15 m from the ball must not be in the contest.
    """
    from restart.simulation.events import FirstContactEvent

    engine = SetPieceEngine()
    attack_contacts, total = 0, 0
    for routine in all_corner_routines():
        program = _program(routine)
        for result in MonteCarloRunner(engine).run(program, 40, root_seed=0).results:
            contact = next((e for e in result.events if isinstance(e, FirstContactEvent)), None)
            if contact is None:
                continue
            total += 1
            attack_contacts += contact.team == "attack"

    assert total > 0
    share = attack_contacts / total
    # Real corners are contested, not conceded: the attack should win a
    # meaningful share of first contacts, well above the old 2-15%.
    assert 0.25 <= share <= 0.75, f"attacking first-contact share {share:.0%}"

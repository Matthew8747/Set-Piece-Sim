"""Trajectory simulator tests: event extraction, terminations, determinism,
and the flagship physical-plausibility recreation (Roberto Carlos 1997)."""

import numpy as np
import pytest

from restart.physics import BallState, IntegratorConfig, PhysicsConfig, TrajectorySimulator
from restart.simulation.events import (
    ApexEvent,
    BounceEvent,
    GoalEvent,
    LaunchEvent,
    TerminationReason,
)


def make_state(
    pos: tuple[float, float, float],
    vel: tuple[float, float, float],
    spin: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> BallState:
    return BallState(position=np.array(pos), velocity=np.array(vel), spin=np.array(spin))


CORNER_DELIVERY = make_state((52.5, -34.0, 0.11), (-8.0, 22.0, 7.5), (0.0, 0.0, 55.0))


class TestEventExtraction:
    def test_event_sequence_for_a_corner_delivery(self) -> None:
        traj = TrajectorySimulator().simulate(CORNER_DELIVERY)
        kinds = [e.kind for e in traj.events]
        assert kinds[0] == "launch"
        assert "apex" in kinds
        assert "bounce" in kinds
        # Apex of the first arc precedes the first bounce.
        assert kinds.index("apex") < kinds.index("bounce")

    def test_event_times_monotonic(self) -> None:
        traj = TrajectorySimulator().simulate(CORNER_DELIVERY)
        times = [e.time_s for e in traj.events]
        assert times == sorted(times)

    def test_launch_event_captures_initial_kinematics(self) -> None:
        traj = TrajectorySimulator().simulate(CORNER_DELIVERY)
        launch = traj.events[0]
        assert isinstance(launch, LaunchEvent)
        assert launch.speed_ms == pytest.approx(CORNER_DELIVERY.speed_ms)

    def test_apex_height_consistent_with_samples(self) -> None:
        traj = TrajectorySimulator().simulate(CORNER_DELIVERY)
        apexes = [e for e in traj.events if isinstance(e, ApexEvent)]
        # Interpolated apex may exceed the sampled max by a hair; never lag far.
        assert max(float(a.position[2]) for a in apexes) == pytest.approx(
            traj.apex_height_m, abs=0.02
        )

    def test_bounce_events_record_energy_loss(self) -> None:
        traj = TrajectorySimulator().simulate(CORNER_DELIVERY)
        for e in traj.events:
            if isinstance(e, BounceEvent):
                assert 0.0 < e.energy_retained < 1.0
                assert e.impact_speed_ms > 0.0


class TestTerminations:
    def test_straight_drive_scores(self) -> None:
        """28 m/s drive from 12.5 m out, on target: must be a GOAL."""
        traj = TrajectorySimulator().simulate(make_state((40.0, 0.0, 0.11), (28.0, 0.0, 4.0)))
        assert traj.termination is TerminationReason.GOAL
        assert traj.goal_scored
        goal = traj.events[-1]
        assert isinstance(goal, GoalEvent)
        assert abs(goal.entry_y_m) < 3.66
        assert 0.0 <= goal.entry_z_m <= 2.44

    def test_shot_over_the_bar_is_out_of_play(self) -> None:
        traj = TrajectorySimulator().simulate(make_state((40.0, 0.0, 0.11), (25.0, 0.0, 14.0)))
        assert traj.termination is TerminationReason.OUT_OF_PLAY
        assert traj.events[-1].kind == "outofplay"

    def test_wide_shot_is_out_of_play(self) -> None:
        traj = TrajectorySimulator().simulate(make_state((40.0, 8.0, 0.11), (25.0, 10.0, 4.0)))
        assert traj.termination is TerminationReason.OUT_OF_PLAY

    def test_ball_over_touchline(self) -> None:
        traj = TrajectorySimulator().simulate(make_state((0.0, 30.0, 0.11), (0.0, 20.0, 5.0)))
        assert traj.termination is TerminationReason.OUT_OF_PLAY

    def test_soft_pass_rolls_to_rest(self) -> None:
        traj = TrajectorySimulator().simulate(make_state((0.0, 0.0, 0.11), (4.0, 0.0, 0.5)))
        assert traj.termination is TerminationReason.REST
        assert traj.events[-1].kind == "rest"
        assert traj.final_state.speed_ms == pytest.approx(0.0, abs=1e-9)

    def test_max_time_cap(self) -> None:
        cfg = PhysicsConfig(integrator=IntegratorConfig(max_flight_time_s=1.0))
        traj = TrajectorySimulator(cfg).simulate(CORNER_DELIVERY)
        assert traj.termination is TerminationReason.MAX_TIME
        assert traj.final_state.time_s <= 1.0 + cfg.integrator.dt_s


class TestDeterminismAndSamples:
    def test_bitwise_deterministic(self) -> None:
        a = TrajectorySimulator().simulate(CORNER_DELIVERY)
        b = TrajectorySimulator().simulate(CORNER_DELIVERY)
        np.testing.assert_array_equal(a.samples.positions, b.samples.positions)
        np.testing.assert_array_equal(a.samples.times_s, b.samples.times_s)
        assert [e.kind for e in a.events] == [e.kind for e in b.events]
        assert a.termination == b.termination

    def test_samples_are_read_only(self) -> None:
        traj = TrajectorySimulator().simulate(CORNER_DELIVERY)
        with pytest.raises(ValueError, match="read-only"):
            traj.samples.positions[0, 0] = 99.0

    def test_samples_shapes_consistent(self) -> None:
        traj = TrajectorySimulator().simulate(CORNER_DELIVERY)
        n = len(traj.samples)
        assert traj.samples.times_s.shape == (n,)
        assert traj.samples.positions.shape == (n, 3)
        assert traj.samples.velocities.shape == (n, 3)
        assert traj.samples.spins.shape == (n, 3)
        assert n > 100  # dense replay data, not a stub


class TestSpinPhysics:
    def test_sidespin_bends_the_flight(self) -> None:
        """Identical launches, +/- z-spin: lateral separation must be large."""
        base_v = (30.0, 0.0, 8.0)
        left = TrajectorySimulator().simulate(
            make_state((0.0, 0.0, 0.11), base_v, (0.0, 0.0, 60.0))
        )
        right = TrajectorySimulator().simulate(
            make_state((0.0, 0.0, 0.11), base_v, (0.0, 0.0, -60.0))
        )
        i = min(len(left.samples), len(right.samples)) - 1
        separation = abs(float(left.samples.positions[i, 1] - right.samples.positions[i, 1]))
        assert separation > 4.0

    def test_roberto_carlos_1997_bends_around_the_wall(self) -> None:
        """The Tournoi free kick: ~35 m out, ~38 m/s, heavy sidespin.

        Physical-plausibility gate (V1): the same strike without spin flies
        ~straight; with spin it must deviate laterally by 2-9 m by the time it
        reaches the goal-line plane (published reconstructions estimate ~4 m).
        """
        pos = (17.5, 0.0, 0.11)
        vel = (36.5, -6.0, 7.2)  # aimed ~9 degrees wide of the near post
        spin = (0.0, 0.0, 88.0)  # curls back toward goal (+y)

        straight = TrajectorySimulator().simulate(make_state(pos, vel))
        bent = TrajectorySimulator().simulate(make_state(pos, vel, spin))

        def y_at_goal_plane(samples_positions: np.ndarray) -> float:
            xs = samples_positions[:, 0]
            idx = int(np.argmax(xs >= 52.0))
            return float(samples_positions[idx, 1])

        y_straight = y_at_goal_plane(np.asarray(straight.samples.positions))
        y_bent = y_at_goal_plane(np.asarray(bent.samples.positions))

        deflection = y_bent - y_straight
        assert 2.0 < deflection < 9.0  # bends, toward the spin side, plausibly

"""Tests for restart.agents.kinematics — invariant properties and correctness."""

import numpy as np
import pytest

from restart.agents.kinematics import separate, step_agents, time_to_point

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DT = 0.02
_TURN_RATE = 8.0
_SPEED_REF = 4.0
_ARRIVAL = 0.3
_SEP_RADIUS = 0.4


def _step(
    pos: np.ndarray,
    vel: np.ndarray,
    targets: np.ndarray,
    top_speed: np.ndarray,
    accel: np.ndarray,
    agility: np.ndarray,
    dt: float = _DT,
) -> tuple[np.ndarray, np.ndarray]:
    return step_agents(
        pos,
        vel,
        targets,
        top_speed,
        accel,
        agility,
        dt,
        turn_rate_base=_TURN_RATE,
        speed_ref=_SPEED_REF,
        arrival_radius=_ARRIVAL,
    )


# ---------------------------------------------------------------------------
# step_agents
# ---------------------------------------------------------------------------


class TestStepAgentsSpeedInvariant:
    """Speed never exceeds top_speed after a step."""

    @pytest.mark.parametrize("n", [1, 5, 22])
    def test_speed_never_exceeds_top_speed(self, n: int) -> None:
        rng = np.random.default_rng(0)
        pos = rng.uniform(-10.0, 10.0, (n, 2))
        vel = rng.uniform(-6.0, 6.0, (n, 2))
        targets = rng.uniform(-20.0, 20.0, (n, 2))
        top_speed = rng.uniform(6.0, 9.0, (n,))
        accel = rng.uniform(3.0, 7.0, (n,))
        agility = rng.uniform(0.0, 1.0, (n,))

        _, vel_new = _step(pos, vel, targets, top_speed, accel, agility)
        speed_new = np.sqrt(np.sum(vel_new**2, axis=-1))
        assert np.all(
            speed_new <= top_speed + 1e-9
        ), f"speed exceeded top_speed: max excess = {np.max(speed_new - top_speed):.6f}"


class TestStepAgentsAccelInvariant:
    """Per-tick velocity change magnitude never exceeds accel*dt (plus float tolerance)."""

    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_accel_budget_respected(self, seed: int) -> None:
        n = 11
        rng = np.random.default_rng(seed)
        pos = rng.uniform(-5.0, 5.0, (n, 2))
        vel = rng.uniform(-4.0, 4.0, (n, 2))
        targets = rng.uniform(-15.0, 15.0, (n, 2))
        top_speed = np.full(n, 8.0)
        accel = rng.uniform(2.0, 7.0, (n,))
        agility = rng.uniform(0.0, 1.0, (n,))

        _, vel_new = _step(pos, vel, targets, top_speed, accel, agility)
        dv = np.sqrt(np.sum((vel_new - vel) ** 2, axis=-1))
        assert np.all(
            dv <= accel * _DT * (1 + 1e-9)
        ), f"velocity change exceeded accel*dt: max excess = {np.max(dv - accel * _DT):.6f}"


class TestStepAgentsTurnClamp:
    """A fast-moving agent cannot reverse heading in one tick."""

    def test_heading_change_limited_for_fast_agent(self) -> None:
        # One agent moving fast in +x direction, target is directly behind (-x)
        pos = np.array([[0.0, 0.0]])
        vel = np.array([[8.0, 0.0]])  # moving in +x at top speed
        targets = np.array([[-100.0, 0.0]])  # wants to go -x
        top_speed = np.array([8.0])
        accel = np.array([5.0])
        agility = np.array([0.5])

        _, vel_new = _step(pos, vel, targets, top_speed, accel, agility)

        heading_old = np.arctan2(vel[0, 1], vel[0, 0])
        heading_new = np.arctan2(vel_new[0, 1], vel_new[0, 0])
        delta = abs(heading_new - heading_old)
        delta = min(delta, 2 * np.pi - delta)  # wrap to [0, pi]

        max_allowed = _DT * _TURN_RATE * (0.25 + 0.75 * 0.5) * _SPEED_REF / (8.0 + _SPEED_REF)
        # heading change must be <= max_allowed (with generous tolerance for the speed clamp)
        assert (
            delta <= max_allowed + 1e-9
        ), f"heading changed by {np.degrees(delta):.2f}° but max is {np.degrees(max_allowed):.2f}°"

    def test_slow_agent_can_turn_freely(self) -> None:
        """Agent at speed < 0.5 m/s should be able to turn in any direction."""
        pos = np.array([[0.0, 0.0]])
        vel = np.array([[0.1, 0.0]])  # very slow
        targets = np.array([[0.0, 10.0]])  # perpendicular
        top_speed = np.array([8.0])
        accel = np.array([5.0])
        agility = np.array([0.5])

        _, vel_new = _step(pos, vel, targets, top_speed, accel, agility)
        # Should be moving mostly in +y direction now
        assert vel_new[0, 1] > vel_new[0, 0]


class TestStepAgentsArrival:
    """Agent settles within arrival radius and stays there."""

    def test_agent_arrives_and_holds(self) -> None:
        n = 1
        pos = np.array([[0.0, 0.0]])
        targets = np.array([[0.5, 0.0]])  # just outside arrival radius
        vel = np.zeros((n, 2))
        top_speed = np.array([8.0])
        accel = np.array([10.0])
        agility = np.array([0.8])

        # Run enough ticks for agent to arrive
        for _ in range(200):
            pos, vel = _step(pos, vel, targets, top_speed, accel, agility)

        dist = float(np.sqrt(np.sum((pos - targets) ** 2)))
        assert dist <= _ARRIVAL + 1e-3, f"agent not within arrival radius: dist = {dist:.4f}"

    def test_agent_holds_after_arrival(self) -> None:
        """Once arrived, agent should stay within arrival radius."""
        pos = np.array([[0.29, 0.0]])  # already inside arrival radius
        targets = np.array([[0.0, 0.0]])
        vel = np.zeros((1, 2))
        top_speed = np.array([8.0])
        accel = np.array([5.0])
        agility = np.array([0.5])

        for _ in range(50):
            pos, vel = _step(pos, vel, targets, top_speed, accel, agility)

        dist = float(np.sqrt(np.sum((pos - targets) ** 2)))
        assert dist <= _ARRIVAL + 1e-3


class TestStepAgentsPurity:
    """step_agents must not mutate its inputs."""

    def test_inputs_not_mutated(self) -> None:
        n = 3
        rng = np.random.default_rng(99)
        pos = rng.uniform(-5.0, 5.0, (n, 2))
        vel = rng.uniform(-3.0, 3.0, (n, 2))
        targets = rng.uniform(-10.0, 10.0, (n, 2))
        top_speed = np.full(n, 8.0)
        accel = np.full(n, 5.0)
        agility = np.full(n, 0.5)

        pos_copy = pos.copy()
        vel_copy = vel.copy()
        _step(pos, vel, targets, top_speed, accel, agility)

        np.testing.assert_array_equal(pos, pos_copy)
        np.testing.assert_array_equal(vel, vel_copy)


# ---------------------------------------------------------------------------
# time_to_point
# ---------------------------------------------------------------------------


class TestTimeToPoint:
    def test_at_target_returns_zero(self) -> None:
        pos = np.array([[5.0, 5.0]])
        vel = np.zeros((1, 2))
        point = np.array([5.0, 5.0])
        t = time_to_point(pos, vel, point, np.array([8.0]), np.array([5.0]))
        assert float(t[0]) == pytest.approx(0.0, abs=1e-9)

    def test_stationary_agent_straight_line_within_5pct(self) -> None:
        """Analytical estimate matches simulation within 5% for straight line."""
        pos = np.array([[0.0, 0.0]])
        vel = np.zeros((1, 2))
        point = np.array([20.0, 0.0])
        top_speed = np.array([8.0])
        accel = np.array([4.0])

        t_est = float(time_to_point(pos, vel, point, top_speed, accel)[0])

        # Simulate to measure actual time
        sim_pos = np.array([[0.0, 0.0]])
        sim_vel = np.zeros((1, 2))
        sim_top = np.array([8.0])
        sim_accel = np.array([4.0])
        sim_agility = np.array([0.5])
        dt = 0.001
        t_sim = 0.0
        for _ in range(100_000):
            sim_pos, sim_vel = step_agents(
                sim_pos,
                sim_vel,
                np.array([[20.0, 0.0]]),
                sim_top,
                sim_accel,
                sim_agility,
                dt,
                turn_rate_base=_TURN_RATE,
                speed_ref=_SPEED_REF,
                arrival_radius=0.01,
            )
            t_sim += dt
            if float(np.linalg.norm(sim_pos - np.array([[20.0, 0.0]]))) <= 0.05:
                break

        assert t_est == pytest.approx(
            t_sim, rel=0.05
        ), f"estimate {t_est:.3f}s vs simulation {t_sim:.3f}s"

    def test_already_moving_toward_target(self) -> None:
        """Agent with initial velocity toward target should have shorter estimate."""
        pos = np.zeros((1, 2))
        vel_fast = np.array([[4.0, 0.0]])
        vel_zero = np.zeros((1, 2))
        point = np.array([30.0, 0.0])
        top_speed = np.array([8.0])
        accel = np.array([4.0])

        t_fast = float(time_to_point(pos, vel_fast, point, top_speed, accel)[0])
        t_zero = float(time_to_point(pos, vel_zero, point, top_speed, accel)[0])
        assert t_fast < t_zero

    def test_broadcast_single_point(self) -> None:
        """(2,) point broadcasts correctly over (n, 2) agents."""
        n = 5
        pos = np.zeros((n, 2))
        vel = np.zeros((n, 2))
        point = np.array([10.0, 0.0])
        top_speed = np.full(n, 8.0)
        accel = np.full(n, 4.0)
        t = time_to_point(pos, vel, point, top_speed, accel)
        assert t.shape == (n,)
        # All identical agents → same times
        assert np.allclose(t, t[0])


# ---------------------------------------------------------------------------
# separate
# ---------------------------------------------------------------------------


class TestSeparate:
    def test_resolves_overlapping_pair(self) -> None:
        """Two overlapping agents should be >= 2*radius apart after separation."""
        radius = 0.4
        pos = np.array([[0.0, 0.0], [0.3, 0.0]])  # dist=0.3 < 2*0.4=0.8
        out = separate(pos, radius)
        dist = float(np.sqrt(np.sum((out[1] - out[0]) ** 2)))
        assert dist >= 2.0 * radius - 1e-9, f"agents still overlap: dist={dist:.4f}"

    def test_non_overlapping_unchanged(self) -> None:
        """Well-separated agents should not be moved."""
        radius = 0.4
        pos = np.array([[0.0, 0.0], [2.0, 0.0]])  # dist=2.0 >> 2*0.4
        out = separate(pos, radius)
        np.testing.assert_allclose(out, pos)

    def test_deterministic(self) -> None:
        """Two calls with identical input produce identical output."""
        radius = 0.4
        pos = np.array([[0.0, 0.0], [0.2, 0.1], [0.5, 0.5]])
        out1 = separate(pos, radius)
        out2 = separate(pos, radius)
        np.testing.assert_array_equal(out1, out2)

    def test_zero_distance_pair_resolved(self) -> None:
        """Two agents at identical positions should be pushed apart."""
        radius = 0.4
        pos = np.array([[1.0, 1.0], [1.0, 1.0]])
        out = separate(pos, radius)
        dist = float(np.sqrt(np.sum((out[1] - out[0]) ** 2)))
        assert dist >= 2.0 * radius - 1e-9

    def test_purity(self) -> None:
        """separate must not mutate the input array."""
        radius = 0.4
        pos = np.array([[0.0, 0.0], [0.3, 0.0]])
        pos_copy = pos.copy()
        separate(pos, radius)
        np.testing.assert_array_equal(pos, pos_copy)

    @pytest.mark.parametrize("n", [3, 11, 22])
    def test_all_pairs_separated_after_pass(self, n: int) -> None:
        """After one pass, all pairs are at least 2*radius apart (dense cluster)."""
        radius = 0.4
        # All agents piled at origin
        pos = np.zeros((n, 2))
        out = separate(pos, radius)
        for i in range(n):
            for j in range(i + 1, n):
                dist = float(np.sqrt(np.sum((out[j] - out[i]) ** 2)))
                assert (
                    dist >= 2.0 * radius - 1e-9
                ), f"pair ({i},{j}) still overlaps: dist={dist:.4f}"

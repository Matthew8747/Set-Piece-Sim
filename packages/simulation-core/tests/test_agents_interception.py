"""Tests for restart.agents.interception - feasibility, gating, and determinism."""

import numpy as np

from restart.agents.interception import earliest_interception

# ---------------------------------------------------------------------------
# Helpers to build minimal ball-flight tables
# ---------------------------------------------------------------------------


def _ball_table(
    positions: list[tuple[float, float, float]],
    start_time: float = 0.0,
    dt: float = 0.1,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (ball_times (m,), ball_pos (m, 3)) for a list of (x, y, z) samples."""
    m = len(positions)
    times = np.array([start_time + i * dt for i in range(m)], dtype=np.float64)
    pos = np.array(positions, dtype=np.float64)
    return times, pos


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEarliestInterceptionStationary:
    """Stationary ball directly at an agent - should intercept at first reachable sample."""

    def test_stationary_ball_at_agent_intercepts_immediately(self) -> None:
        # Agent at (5, 5), ball hovering at (5, 5, 1.0)
        n = 1
        pos = np.array([[5.0, 5.0]])
        vel = np.zeros((n, 2))
        top_speed = np.array([8.0])
        accel = np.array([5.0])
        reach = np.array([2.5])
        ready_time = np.array([0.0])

        ball_times, ball_pos = _ball_table([(5.0, 5.0, 1.0)] * 10)

        result = earliest_interception(
            pos, vel, top_speed, accel, reach, ready_time, ball_times, ball_pos
        )
        assert result[0] == 0, f"expected index 0, got {result[0]}"

    def test_stationary_ball_after_reaction_delay(self) -> None:
        """Agent with reaction delay should pick up first sample at/after ready_time."""
        n = 1
        pos = np.array([[0.0, 0.0]])
        vel = np.zeros((n, 2))
        top_speed = np.array([8.0])
        accel = np.array([5.0])
        reach = np.array([2.5])
        # Ready at t=0.35 s
        ready_time = np.array([0.35])

        ball_times, ball_pos = _ball_table([(0.0, 0.0, 1.0)] * 20, start_time=0.0, dt=0.1)
        # Samples at 0.0, 0.1, 0.2, 0.3, 0.4, …  ready at 0.35 → first valid = index 4 (t=0.4)

        result = earliest_interception(
            pos, vel, top_speed, accel, reach, ready_time, ball_times, ball_pos
        )
        assert result[0] == 4, f"expected index 4, got {result[0]}"


class TestEarliestInterceptionUnreachable:
    """Returns -1 when ball is unreachable (too fast or too high)."""

    def test_ball_too_fast_returns_minus_one(self) -> None:
        """Ball moves so fast that agent can never arrive in time."""
        n = 1
        pos = np.array([[0.0, 0.0]])
        vel = np.zeros((n, 2))
        top_speed = np.array([1.0])  # very slow agent
        accel = np.array([0.5])
        reach = np.array([3.0])
        ready_time = np.array([0.0])

        # Ball 100 m away, samples close together in time - agent can never catch it
        samples = [(100.0 + i * 10.0, 0.0, 1.0) for i in range(20)]
        ball_times = np.arange(20, dtype=np.float64) * 0.01  # 0 to 0.19 s - no time to run 100m
        ball_pos = np.array(samples, dtype=np.float64)

        result = earliest_interception(
            pos, vel, top_speed, accel, reach, ready_time, ball_times, ball_pos
        )
        assert result[0] == -1

    def test_ball_too_high_returns_minus_one(self) -> None:
        """Ball height exceeds agent's reach on all samples."""
        n = 1
        pos = np.array([[0.0, 0.0]])
        vel = np.zeros((n, 2))
        top_speed = np.array([9.0])
        accel = np.array([8.0])
        reach = np.array([2.0])  # reach 2.0 m
        ready_time = np.array([0.0])

        ball_times, ball_pos = _ball_table([(0.0, 0.0, 3.0)] * 10)  # z=3.0 > reach=2.0

        result = earliest_interception(
            pos, vel, top_speed, accel, reach, ready_time, ball_times, ball_pos
        )
        assert result[0] == -1


class TestEarliestInterceptionReactionOrdering:
    """Earlier-ready agent intercepts earlier sample than late-reaction agent."""

    def test_earlier_ready_agent_intercepts_earlier_sample(self) -> None:
        n = 2
        pos = np.array([[0.0, 0.0], [0.0, 0.0]])  # same position
        vel = np.zeros((n, 2))
        top_speed = np.full(n, 8.0)
        accel = np.full(n, 5.0)
        reach = np.full(n, 2.5)
        # Agent 0: ready at t=0.0; agent 1: ready at t=0.5
        ready_time = np.array([0.0, 0.5])

        # Ball hovers at same location, samples at t=0.0, 0.1, 0.2, ... 0.9
        ball_times, ball_pos = _ball_table([(0.0, 0.0, 1.0)] * 10, start_time=0.0, dt=0.1)

        result = earliest_interception(
            pos, vel, top_speed, accel, reach, ready_time, ball_times, ball_pos
        )
        # Agent 0 should get index 0, agent 1 should get index 5 (first at t>=0.5)
        assert result[0] == 0
        assert result[1] == 5
        assert result[0] < result[1]


class TestEarliestInterceptionDeterminism:
    """Same inputs always produce same output."""

    def test_deterministic(self) -> None:
        n = 5
        rng = np.random.default_rng(42)
        pos = rng.uniform(-10.0, 10.0, (n, 2))
        vel = rng.uniform(-2.0, 2.0, (n, 2))
        top_speed = rng.uniform(6.0, 9.0, (n,))
        accel = rng.uniform(3.0, 7.0, (n,))
        reach = rng.uniform(2.2, 3.0, (n,))
        ready_time = rng.uniform(0.0, 0.5, (n,))

        m = 30
        ball_times = np.linspace(0.0, 3.0, m)
        ball_x = np.linspace(-5.0, 5.0, m)
        ball_y = np.zeros(m)
        ball_z = rng.uniform(0.5, 3.0, m)
        ball_pos = np.column_stack([ball_x, ball_y, ball_z])

        r1 = earliest_interception(
            pos, vel, top_speed, accel, reach, ready_time, ball_times, ball_pos
        )
        r2 = earliest_interception(
            pos, vel, top_speed, accel, reach, ready_time, ball_times, ball_pos
        )
        np.testing.assert_array_equal(r1, r2)


class TestEarliestInterceptionReturnShape:
    """Output shape is (n,) int64."""

    def test_output_shape_and_dtype(self) -> None:
        n = 7
        pos = np.zeros((n, 2))
        vel = np.zeros((n, 2))
        top_speed = np.full(n, 8.0)
        accel = np.full(n, 5.0)
        reach = np.full(n, 2.5)
        ready_time = np.zeros(n)

        ball_times, ball_pos = _ball_table([(0.0, 0.0, 1.0)] * 5)

        result = earliest_interception(
            pos, vel, top_speed, accel, reach, ready_time, ball_times, ball_pos
        )
        assert result.shape == (n,)
        assert result.dtype == np.int64


class TestEarliestInterceptionMultiAgent:
    """Agents at different distances intercept different samples."""

    def test_close_agent_intercepts_earlier(self) -> None:
        n = 2
        # Agent 0: at the ball origin; agent 1: 50 m away
        pos = np.array([[0.0, 0.0], [50.0, 0.0]])
        vel = np.zeros((n, 2))
        top_speed = np.full(n, 8.0)
        accel = np.full(n, 5.0)
        reach = np.full(n, 3.0)
        ready_time = np.zeros(n)

        # Ball moves slowly along x, samples at t=0, 0.5, 1.0, ...
        m = 20
        ball_times = np.arange(m, dtype=np.float64) * 0.5
        ball_x = np.arange(m, dtype=np.float64) * 1.0  # slow movement
        ball_pos = np.column_stack([ball_x, np.zeros(m), np.ones(m)])

        result = earliest_interception(
            pos, vel, top_speed, accel, reach, ready_time, ball_times, ball_pos
        )
        # Agent 0 should intercept earlier (lower index) than agent 1
        if result[0] >= 0 and result[1] >= 0:
            assert result[0] <= result[1]
        # Agent 0 must be able to intercept (it starts right at the ball)
        assert result[0] >= 0

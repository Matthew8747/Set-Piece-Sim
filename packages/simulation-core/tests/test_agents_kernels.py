"""njit agent kernels must reproduce the NumPy references to <=1e-9 (ADR-011).

Same discipline as physics/_kernels.py: the readable broadcast NumPy functions
in agents/kinematics.py define the semantics; the scalar-loop njit ports in
agents/_kernels.py are the throughput path the fused scenario kernel (Phase 10)
will call. This test is the equivalence contract that polices drift between them.
"""

import numpy as np

from restart.agents import _kernels
from restart.agents.interception import earliest_interception
from restart.agents.kinematics import step_agents, time_to_point


def _ball_flight(m: int = 60) -> tuple[np.ndarray, np.ndarray]:
    """A simple lofted arc sampled at 20 ms: (ball_times (m,), ball_pos (m, 3))."""
    t = np.arange(m) * 0.02
    x = 52.5 - 8.0 * t
    y = -33.7 + 18.0 * t
    z = np.maximum(0.11, 0.11 + 12.0 * t - 0.5 * 9.81 * t * t)
    return t, np.stack([x, y, z], axis=1)


def _rng_state(n: int, seed: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    return {
        "pos": rng.uniform(-30.0, 30.0, (n, 2)),
        "vel": rng.uniform(-8.0, 8.0, (n, 2)),
        "targets": rng.uniform(-30.0, 30.0, (n, 2)),
        "top_speed": rng.uniform(5.0, 9.0, n),
        "accel": rng.uniform(2.0, 6.0, n),
        "agility": rng.uniform(0.3, 0.95, n),
    }


# Representative AgentConfig design point (config.py defaults).
TURN_RATE_BASE = 8.0
SPEED_REF = 4.0
ARRIVAL_RADIUS = 0.3
DT = 0.02


class TestStepAgentsEquivalence:
    def test_matches_numpy_reference(self) -> None:
        for seed in range(8):
            s = _rng_state(22, seed)
            ref_pos, ref_vel = step_agents(
                s["pos"],
                s["vel"],
                s["targets"],
                s["top_speed"],
                s["accel"],
                s["agility"],
                DT,
                turn_rate_base=TURN_RATE_BASE,
                speed_ref=SPEED_REF,
                arrival_radius=ARRIVAL_RADIUS,
            )
            k_pos, k_vel = _kernels.step_agents_kernel(
                s["pos"],
                s["vel"],
                s["targets"],
                s["top_speed"],
                s["accel"],
                s["agility"],
                DT,
                TURN_RATE_BASE,
                SPEED_REF,
                ARRIVAL_RADIUS,
            )
            np.testing.assert_allclose(k_pos, ref_pos, atol=1e-9, rtol=0.0)
            np.testing.assert_allclose(k_vel, ref_vel, atol=1e-9, rtol=0.0)

    def test_zero_velocity_agents(self) -> None:
        # Slow/stationary agents take the can_turn_free branch — exercise it.
        s = _rng_state(10, 99)
        s["vel"][:] = 0.0
        ref_pos, ref_vel = step_agents(
            s["pos"],
            s["vel"],
            s["targets"],
            s["top_speed"],
            s["accel"],
            s["agility"],
            DT,
            turn_rate_base=TURN_RATE_BASE,
            speed_ref=SPEED_REF,
            arrival_radius=ARRIVAL_RADIUS,
        )
        k_pos, k_vel = _kernels.step_agents_kernel(
            s["pos"],
            s["vel"],
            s["targets"],
            s["top_speed"],
            s["accel"],
            s["agility"],
            DT,
            TURN_RATE_BASE,
            SPEED_REF,
            ARRIVAL_RADIUS,
        )
        np.testing.assert_allclose(k_pos, ref_pos, atol=1e-9, rtol=0.0)
        np.testing.assert_allclose(k_vel, ref_vel, atol=1e-9, rtol=0.0)

    def test_does_not_mutate_inputs(self) -> None:
        s = _rng_state(12, 3)
        pos0, vel0 = s["pos"].copy(), s["vel"].copy()
        _kernels.step_agents_kernel(
            s["pos"],
            s["vel"],
            s["targets"],
            s["top_speed"],
            s["accel"],
            s["agility"],
            DT,
            TURN_RATE_BASE,
            SPEED_REF,
            ARRIVAL_RADIUS,
        )
        np.testing.assert_array_equal(s["pos"], pos0)
        np.testing.assert_array_equal(s["vel"], vel0)


class TestTimeToPointEquivalence:
    def test_matches_numpy_reference(self) -> None:
        for seed in range(8):
            s = _rng_state(22, seed)
            ref = time_to_point(s["pos"], s["vel"], s["targets"], s["top_speed"], s["accel"])
            got = _kernels.time_to_point_kernel(
                s["pos"], s["vel"], s["targets"], s["top_speed"], s["accel"]
            )
            np.testing.assert_allclose(got, ref, atol=1e-9, rtol=0.0)

    def test_already_at_target_is_zero(self) -> None:
        s = _rng_state(6, 1)
        s["targets"][:] = s["pos"]  # coincident
        got = _kernels.time_to_point_kernel(
            s["pos"], s["vel"], s["targets"], s["top_speed"], s["accel"]
        )
        np.testing.assert_array_equal(got, np.zeros(6))


class TestEarliestInterceptionEquivalence:
    def test_matches_numpy_reference(self) -> None:
        ball_times, ball_pos = _ball_flight(60)
        for seed in range(8):
            s = _rng_state(22, seed)
            rng = np.random.default_rng(seed + 100)
            reach = rng.uniform(2.0, 3.0, 22)
            ready = rng.uniform(0.0, 0.4, 22)
            ref = earliest_interception(
                s["pos"], s["vel"], s["top_speed"], s["accel"], reach, ready, ball_times, ball_pos
            )
            got = _kernels.earliest_interception_kernel(
                s["pos"], s["vel"], s["top_speed"], s["accel"], reach, ready, ball_times, ball_pos
            )
            np.testing.assert_array_equal(got, ref)

    def test_unreachable_agents_are_minus_one(self) -> None:
        ball_times, ball_pos = _ball_flight(40)
        # Agents far away with low reach and late readiness cannot intercept.
        pos = np.full((5, 2), 100.0)
        vel = np.zeros((5, 2))
        top_speed = np.full(5, 6.0)
        accel = np.full(5, 3.0)
        reach = np.full(5, 0.5)
        ready = np.full(5, 5.0)
        got = _kernels.earliest_interception_kernel(
            pos, vel, top_speed, accel, reach, ready, ball_times, ball_pos
        )
        np.testing.assert_array_equal(got, np.full(5, -1, dtype=np.int64))

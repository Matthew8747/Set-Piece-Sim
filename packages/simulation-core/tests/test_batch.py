"""Batch flight engine tests: consistency with the single-trajectory path,
determinism, masking semantics, and input validation."""

import numpy as np
import pytest

from restart.physics import (
    BallState,
    Gravity,
    IntegratorConfig,
    PhysicsConfig,
    TrajectorySimulator,
    simulate_flights,
)
from restart.physics.analytic import drag_free_apex
from restart.physics.state import pack_states
from restart.simulation.events import BounceEvent


def lofted_batch(n: int, seed: int = 3) -> np.ndarray:
    """Random lofted deliveries that land well inside the pitch."""
    rng = np.random.default_rng(seed)
    pos = np.zeros((n, 3))
    pos[:, 0] = rng.uniform(-20.0, 20.0, n)
    pos[:, 1] = rng.uniform(-15.0, 15.0, n)
    pos[:, 2] = 0.11
    vel = np.zeros((n, 3))
    vel[:, 0] = rng.uniform(-12.0, 12.0, n)
    vel[:, 1] = rng.uniform(-12.0, 12.0, n)
    vel[:, 2] = rng.uniform(6.0, 14.0, n)
    spin = rng.normal(0.0, 30.0, (n, 3))
    return pack_states(pos, vel, spin)


class TestKernelEquivalence:
    """The JIT kernel must reproduce the NumPy reference (ADR-001 addendum)."""

    def test_kernel_matches_numpy_reference(self) -> None:
        from restart.physics.batch import _simulate_flights_numpy

        batch = lofted_batch(100, seed=17)
        cfg = PhysicsConfig.default()
        fast = simulate_flights(batch, cfg)
        ref = _simulate_flights_numpy(batch.copy(), cfg)

        np.testing.assert_array_equal(fast.landed, ref.landed)
        np.testing.assert_allclose(fast.landing_position, ref.landing_position, atol=1e-9)
        np.testing.assert_allclose(fast.landing_velocity, ref.landing_velocity, atol=1e-9)
        np.testing.assert_allclose(fast.landing_spin, ref.landing_spin, atol=1e-9)
        np.testing.assert_allclose(fast.landing_time_s, ref.landing_time_s, atol=1e-9)
        np.testing.assert_allclose(fast.apex_height_m, ref.apex_height_m, atol=1e-9)


class TestValidation:
    def test_wrong_shape_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"\(n, 9\)"):
            simulate_flights(np.zeros((4, 6)))

    def test_one_dimensional_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"\(n, 9\)"):
            simulate_flights(np.zeros(9))


class TestConsistencyWithSingleTrajectory:
    def test_landing_matches_first_bounce_of_trajectory_sim(self) -> None:
        """The batch engine and the event simulator must agree on first
        ground contact to floating-point noise - same kernels, same dt."""
        batch = lofted_batch(5)
        result = simulate_flights(batch)
        sim = TrajectorySimulator()

        for i in range(5):
            state = BallState(position=batch[i, 0:3], velocity=batch[i, 3:6], spin=batch[i, 6:9])
            traj = sim.simulate(state)
            first_bounce = next(e for e in traj.events if isinstance(e, BounceEvent))
            # Kernel vs NumPy trajectory machinery: identical semantics, fp
            # reordering only (equivalence contract is 1e-9; allow 1e-7 here
            # for the two layers of independent drift).
            np.testing.assert_allclose(result.landing_position[i], first_bounce.position, atol=1e-7)
            assert result.landing_time_s[i] == pytest.approx(first_bounce.time_s, abs=1e-7)

    def test_apex_matches_drag_free_analytic_with_gravity_only(self) -> None:
        cfg = PhysicsConfig.default()
        y0 = pack_states(
            np.array([[0.0, 0.0, 0.11]]),
            np.array([[5.0, 0.0, 12.0]]),
            np.zeros((1, 3)),
        )
        result = simulate_flights(y0, cfg, force=Gravity(cfg.environment))
        _, z_apex = drag_free_apex(0.11, 12.0, cfg.environment.gravity_ms2)
        # Sampled apex lags the true apex by at most one dt of curvature.
        assert float(result.apex_height_m[0]) == pytest.approx(z_apex, abs=1e-3)


class TestSemantics:
    def test_bitwise_deterministic(self) -> None:
        batch = lofted_batch(64)
        a = simulate_flights(batch)
        b = simulate_flights(batch)
        np.testing.assert_array_equal(a.landing_position, b.landing_position)
        np.testing.assert_array_equal(a.landing_time_s, b.landing_time_s)

    def test_input_not_mutated(self) -> None:
        batch = lofted_batch(8)
        snapshot = batch.copy()
        simulate_flights(batch)
        np.testing.assert_array_equal(batch, snapshot)

    def test_all_lofted_flights_land(self) -> None:
        result = simulate_flights(lofted_batch(200))
        assert result.n_sims == 200
        assert bool(result.landed.all())
        assert np.all(np.isfinite(result.landing_time_s))
        # Landed exactly on the ground plane (ball radius).
        np.testing.assert_allclose(result.landing_position[:, 2], 0.11, atol=1e-9)

    def test_unlanded_flights_are_nan_marked(self) -> None:
        cfg = PhysicsConfig(integrator=IntegratorConfig(max_flight_time_s=1.0))
        y0 = pack_states(
            np.array([[0.0, 0.0, 0.11]]),
            np.array([[0.0, 0.0, 30.0]]),  # still rising at t=1
            np.zeros((1, 3)),
        )
        result = simulate_flights(y0, cfg)
        assert not bool(result.landed[0])
        assert np.isnan(result.landing_time_s[0])
        assert np.all(np.isnan(result.landing_position[0]))
        assert result.apex_height_m[0] > 10.0  # apex still tracked

    def test_results_read_only(self) -> None:
        result = simulate_flights(lofted_batch(3))
        with pytest.raises(ValueError, match="read-only"):
            result.landing_time_s[0] = 0.0

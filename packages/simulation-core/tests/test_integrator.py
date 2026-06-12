"""Integrator validation: analytic oracles, SciPy oracle, convergence order.

This is the V1 validation gate from the roadmap (Phase 1 acceptance):
- drag-free flight matches the closed form,
- the full force model matches SciPy DOP853 to < 1 cm over a 40 m delivery,
- global error scales ~ dt^4,
- spin decays exponentially,
- a dropped ball approaches the analytic terminal speed.
"""

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from restart.physics import BallConfig, BallState, EnvironmentConfig, Gravity, PhysicsConfig
from restart.physics.analytic import drag_free_apex, drag_free_position, terminal_speed
from restart.physics.forces import default_force_system
from restart.physics.integrator import make_derivative, rk4_step

BALL = BallConfig()
ENV = EnvironmentConfig()


def integrate(y0: np.ndarray, dt: float, n_steps: int, derivative) -> np.ndarray:  # type: ignore[no-untyped-def]
    y = y0.copy()
    for _ in range(n_steps):
        y = rk4_step(y, dt, derivative)
    return y


class TestDragFreeOracle:
    def test_matches_closed_form(self) -> None:
        """Gravity-only flight must match ballistic algebra to ~1e-10 m."""
        deriv = make_derivative(Gravity(ENV), BALL.spin_decay_tau_s)
        state = BallState(
            position=np.array([0.0, 0.0, 1.0]),
            velocity=np.array([20.0, 5.0, 12.0]),
        )
        y = state.to_vector()
        dt, t_end = 0.005, 1.5
        n = round(t_end / dt)
        y_final = integrate(y, dt, n, deriv)
        expected = drag_free_position(
            state.position, state.velocity, ENV.gravity_ms2, np.array([t_end])
        )[0]
        np.testing.assert_allclose(y_final[0:3], expected, atol=1e-9)

    def test_apex_height(self) -> None:
        deriv = make_derivative(Gravity(ENV), BALL.spin_decay_tau_s)
        vz0 = 14.0
        y = BallState(
            position=np.array([0.0, 0.0, 0.11]), velocity=np.array([0.0, 0.0, vz0])
        ).to_vector()
        t_apex, z_apex = drag_free_apex(0.11, vz0, ENV.gravity_ms2)
        n = round(t_apex / 0.005)
        y_at_apex = integrate(y, 0.005, n, deriv)
        # n*dt lands within one step of t_apex; tolerance covers the residual.
        assert float(y_at_apex[2]) == pytest.approx(z_apex, abs=1e-3)


class TestSciPyOracle:
    def test_full_force_model_within_1cm_over_40m(self) -> None:
        """ADR-002 / P-6 acceptance: RK4 @ 5 ms vs DOP853 @ rtol 1e-10."""
        force = default_force_system(BALL, ENV)
        deriv = make_derivative(force, BALL.spin_decay_tau_s)

        # Out-swinging cross: fast, spinning, ~40 m of travel in ~1.6 s.
        y0 = BallState(
            position=np.array([52.5, -34.0, 0.11]),
            velocity=np.array([-20.0, 18.0, 9.0]),
            spin=np.array([5.0, -3.0, 60.0]),
        ).to_vector()
        t_end = 1.6

        sol = solve_ivp(
            lambda _t, y: deriv(y),
            (0.0, t_end),
            y0,
            method="DOP853",
            rtol=1e-10,
            atol=1e-12,
            dense_output=True,
        )
        assert sol.success
        assert sol.sol is not None
        reference = sol.sol(t_end)

        dt = 0.005
        ours = integrate(y0, dt, round(t_end / dt), deriv)

        distance_travelled = float(np.linalg.norm(ours[0:3] - y0[0:3]))
        assert distance_travelled > 30.0  # a real delivery, not a tap
        position_error = float(np.linalg.norm(ours[0:3] - reference[0:3]))
        assert position_error < 0.01  # < 1 cm


class TestConvergenceOrder:
    def test_rk4_global_error_scales_dt4(self) -> None:
        force = default_force_system(BALL, ENV)
        deriv = make_derivative(force, BALL.spin_decay_tau_s)
        y0 = BallState(
            position=np.array([0.0, 0.0, 0.5]),
            velocity=np.array([25.0, 3.0, 8.0]),
            spin=np.array([0.0, 20.0, 40.0]),
        ).to_vector()
        t_end = 1.0

        ref = integrate(y0, t_end / 4096, 4096, deriv)
        err_coarse = np.linalg.norm(integrate(y0, t_end / 64, 64, deriv)[0:3] - ref[0:3])
        err_fine = np.linalg.norm(integrate(y0, t_end / 128, 128, deriv)[0:3] - ref[0:3])

        ratio = err_coarse / err_fine
        # Exact 4th order gives 16; accept a generous band around it.
        assert 8.0 < ratio < 40.0


class TestSpinDecay:
    def test_exponential_decay_in_state_vector(self) -> None:
        deriv = make_derivative(Gravity(ENV), BALL.spin_decay_tau_s)
        w0 = np.array([10.0, -20.0, 50.0])
        y0 = BallState(
            position=np.zeros(3), velocity=np.array([5.0, 0.0, 20.0]), spin=w0
        ).to_vector()
        t_end, dt = 2.0, 0.005
        y = integrate(y0, dt, round(t_end / dt), deriv)
        expected = w0 * np.exp(-t_end / BALL.spin_decay_tau_s)
        np.testing.assert_allclose(y[6:9], expected, rtol=1e-6)


class TestTerminalSpeed:
    def test_falling_ball_approaches_analytic_terminal(self) -> None:
        """Drop with full drag: v_z -> -v_t = -sqrt(2mg / rho A cd)."""
        cfg = PhysicsConfig.default()
        force = default_force_system(cfg.ball, cfg.environment)
        deriv = make_derivative(force, cfg.ball.spin_decay_tau_s)
        y0 = BallState(position=np.array([0.0, 0.0, 500.0]), velocity=np.zeros(3)).to_vector()
        y = integrate(y0, 0.005, round(12.0 / 0.005), deriv)

        # Terminal speed (~27 m/s) sits far above the drag crisis, so cd there
        # is the supercritical value.
        v_t = terminal_speed(cfg.ball, cfg.environment, cfg.ball.drag.cd_supercritical)
        assert float(-y[5]) == pytest.approx(v_t, rel=0.01)

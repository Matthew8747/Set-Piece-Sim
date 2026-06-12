"""Bounce model tests: restitution, friction branches, spin transfer, and
the energy invariant (property-based)."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from restart.physics import BallConfig, BounceConfig
from restart.physics.bounce import bounce, energy_retained, total_kinetic_energy

BALL = BallConfig()
CFG = BounceConfig()


class TestNormalComponent:
    def test_restitution_reverses_vz(self) -> None:
        v_in = np.array([0.0, 0.0, -10.0])
        v_out, _ = bounce(v_in, np.zeros(3), CFG, BALL)
        assert v_out[2] == pytest.approx(CFG.restitution * 10.0)

    def test_upward_motion_rejected(self) -> None:
        with pytest.raises(ValueError, match="downward"):
            bounce(np.array([1.0, 0.0, 2.0]), np.zeros(3), CFG, BALL)

    def test_inputs_not_mutated(self) -> None:
        v_in = np.array([5.0, 0.0, -8.0])
        w_in = np.array([0.0, 30.0, 0.0])
        bounce(v_in, w_in, CFG, BALL)
        np.testing.assert_array_equal(v_in, [5.0, 0.0, -8.0])
        np.testing.assert_array_equal(w_in, [0.0, 30.0, 0.0])


class TestFrictionAndSpin:
    def test_rolling_contact_has_no_tangential_impulse(self) -> None:
        """A perfectly rolling ball (zero slip) keeps its tangential velocity."""
        vx = 8.0
        w_rolling = np.array([0.0, vx / BALL.radius_m, 0.0])
        v_out, w_out = bounce(np.array([vx, 0.0, -6.0]), w_rolling, CFG, BALL)
        assert v_out[0] == pytest.approx(vx)
        np.testing.assert_allclose(w_out, w_rolling)

    def test_backspin_decelerates_horizontal_motion(self) -> None:
        v_out, _ = bounce(np.array([10.0, 0.0, -6.0]), np.array([0.0, -80.0, 0.0]), CFG, BALL)
        assert v_out[0] < 10.0

    def test_overspun_topspin_accelerates_horizontal_motion(self) -> None:
        """Topspin beyond rolling (shooting forward off the pitch)."""
        vx = 8.0
        w_over = np.array([0.0, 3.0 * vx / BALL.radius_m, 0.0])
        v_out, _ = bounce(np.array([vx, 0.0, -6.0]), w_over, CFG, BALL)
        assert v_out[0] > vx

    def test_backspin_can_reverse_direction(self) -> None:
        """Slow ball + heavy backspin + grippy surface = spin-back."""
        grippy = BounceConfig(friction_mu=0.9)
        v_out, _ = bounce(np.array([1.0, 0.0, -8.0]), np.array([0.0, -120.0, 0.0]), grippy, BALL)
        assert v_out[0] < 0.0

    def test_stick_branch_leaves_zero_slip(self) -> None:
        """When friction can stop the slip, the contact point exits at rest."""
        v_in = np.array([2.0, 0.0, -9.0])  # big j_n, small slip => stick
        w_in = np.zeros(3)
        v_out, w_out = bounce(v_in, w_in, CFG, BALL)
        slip_out = v_out[:2] - BALL.radius_m * np.cross(w_out, [0.0, 0.0, 1.0])[:2]
        np.testing.assert_allclose(slip_out, np.zeros(2), atol=1e-10)

    def test_normal_spin_component_unchanged(self) -> None:
        """No twisting friction (P-9): z-spin survives the bounce."""
        w_in = np.array([10.0, -5.0, 44.0])
        _, w_out = bounce(np.array([6.0, 2.0, -7.0]), w_in, CFG, BALL)
        assert w_out[2] == pytest.approx(44.0)


class TestEnergyInvariant:
    @settings(max_examples=300, deadline=None)
    @given(
        vx=st.floats(-30, 30),
        vy=st.floats(-30, 30),
        vz=st.floats(-25, -0.1),
        wx=st.floats(-150, 150),
        wy=st.floats(-150, 150),
        wz=st.floats(-150, 150),
        e=st.floats(0.30, 0.90),
        mu=st.floats(0.05, 1.0),
    )
    def test_total_kinetic_energy_never_increases(
        self, vx: float, vy: float, vz: float, wx: float, wy: float, wz: float, e: float, mu: float
    ) -> None:
        cfg = BounceConfig(restitution=e, friction_mu=mu)
        v_in = np.array([vx, vy, vz])
        w_in = np.array([wx, wy, wz])
        v_out, w_out = bounce(v_in, w_in, cfg, BALL)

        e_in = total_kinetic_energy(v_in, w_in, BALL)
        e_out = total_kinetic_energy(v_out, w_out, BALL)
        assert e_out <= e_in * (1.0 + 1e-9)

        retained = energy_retained(v_in, w_in, v_out, w_out, BALL)
        assert 0.0 < retained <= 1.0 + 1e-9

    @settings(max_examples=100, deadline=None)
    @given(
        vz=st.floats(-25, -0.1),
        e=st.floats(0.30, 0.90),
    )
    def test_restitution_exact_on_normal_axis(self, vz: float, e: float) -> None:
        cfg = BounceConfig(restitution=e)
        v_out, _ = bounce(np.array([3.0, -2.0, vz]), np.array([20.0, 10.0, -5.0]), cfg, BALL)
        assert v_out[2] == pytest.approx(e * (-vz), rel=1e-12)

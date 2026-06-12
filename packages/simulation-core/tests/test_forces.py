"""Force model tests: directions, magnitudes, regimes, composition."""

import numpy as np
import pytest

from restart.domain.vectors import dot, norm, vec3
from restart.physics import BallConfig, EnvironmentConfig, ForceSystem, Gravity, MagnusLift
from restart.physics.forces import QuadraticDrag, default_force_system
from restart.simulation.interfaces import ForceModel

BALL = BallConfig()
ENV = EnvironmentConfig()
ZERO = np.zeros(3)


class TestGravity:
    def test_constant_minus_z(self) -> None:
        g = Gravity(ENV)
        a = g.acceleration(vec3(10, 5, 3), vec3(30, 0, 10), vec3(0, 0, 50))
        np.testing.assert_allclose(a, [0.0, 0.0, -9.81])

    def test_batch_shape(self) -> None:
        g = Gravity(ENV)
        a = g.acceleration(np.zeros((7, 3)), np.zeros((7, 3)), np.zeros((7, 3)))
        assert a.shape == (7, 3)
        np.testing.assert_allclose(a[:, 2], -9.81)


class TestQuadraticDrag:
    def test_opposes_velocity(self) -> None:
        drag = QuadraticDrag(BALL, ENV)
        v = vec3(20.0, 10.0, 5.0)
        a = drag.acceleration(ZERO, v, ZERO)
        assert float(dot(a, v)) < 0.0
        # Anti-parallel: a x v = 0.
        np.testing.assert_allclose(np.cross(a, v), np.zeros(3), atol=1e-12)

    def test_magnitude_at_high_speed(self) -> None:
        """Well above the crisis, |a| = (rho A / 2m) * cd_super * v^2."""
        drag = QuadraticDrag(BALL, ENV)
        speed = 30.0
        a = drag.acceleration(ZERO, vec3(speed, 0, 0), ZERO)
        k = 0.5 * ENV.air_density_kgm3 * BALL.cross_section_m2 / BALL.mass_kg
        expected = k * BALL.drag.cd_supercritical * speed**2
        assert float(norm(a)) == pytest.approx(expected, rel=1e-3)

    def test_drag_crisis_monotonic_decrease(self) -> None:
        drag = QuadraticDrag(BALL, ENV)
        speeds = np.linspace(2.0, 35.0, 100)
        cds = drag.drag_coefficient(speeds)
        assert np.all(np.diff(cds) < 0.0)
        assert cds[0] == pytest.approx(BALL.drag.cd_subcritical, abs=0.01)
        assert cds[-1] == pytest.approx(BALL.drag.cd_supercritical, abs=0.01)

    def test_zero_velocity_zero_drag(self) -> None:
        drag = QuadraticDrag(BALL, ENV)
        np.testing.assert_allclose(drag.acceleration(ZERO, ZERO, ZERO), np.zeros(3))


class TestMagnusLift:
    def test_perpendicular_to_spin_and_velocity(self) -> None:
        magnus = MagnusLift(BALL, ENV)
        v, w = vec3(25.0, 5.0, 3.0), vec3(2.0, -1.0, 60.0)
        a = magnus.acceleration(ZERO, v, w)
        assert float(dot(a, v)) == pytest.approx(0.0, abs=1e-9)
        assert float(dot(a, w)) == pytest.approx(0.0, abs=1e-9)

    def test_zero_spin_no_force(self) -> None:
        magnus = MagnusLift(BALL, ENV)
        np.testing.assert_array_equal(magnus.acceleration(ZERO, vec3(30, 0, 0), ZERO), np.zeros(3))

    def test_spin_parallel_to_velocity_no_force(self) -> None:
        magnus = MagnusLift(BALL, ENV)
        v = vec3(20.0, 0.0, 0.0)
        a = magnus.acceleration(ZERO, v, 3.0 * v)
        np.testing.assert_allclose(a, np.zeros(3), atol=1e-12)

    def test_topspin_pushes_down(self) -> None:
        """Ball flying +x with topspin (+y spin): w x v points -z (dip)."""
        magnus = MagnusLift(BALL, ENV)
        a = magnus.acceleration(ZERO, vec3(25, 0, 0), vec3(0, 50, 0))
        assert a[2] < 0.0
        assert a[0] == pytest.approx(0.0, abs=1e-12)

    def test_spin_parameter_clamp(self) -> None:
        """Beyond the clamp, more spin must not add more lift."""
        magnus = MagnusLift(BALL, ENV)
        speed = np.asarray(20.0)
        cl_huge = magnus.lift_coefficient(speed, np.asarray(2000.0))
        cl_clamp = magnus.lift_coefficient(
            speed, np.asarray(BALL.magnus.spin_parameter_max * 20.0 / BALL.radius_m)
        )
        assert float(cl_huge) == pytest.approx(float(cl_clamp))


class TestForceSystem:
    def test_sums_components(self) -> None:
        env = ENV
        g, d = Gravity(env), QuadraticDrag(BALL, env)
        system = ForceSystem([g, d])
        v = vec3(15.0, -3.0, 8.0)
        np.testing.assert_allclose(
            system.acceleration(ZERO, v, ZERO),
            g.acceleration(ZERO, v, ZERO) + d.acceleration(ZERO, v, ZERO),
        )

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one force"):
            ForceSystem([])

    def test_name_composition(self) -> None:
        assert default_force_system(BALL, ENV).name == "gravity+drag+magnus"

    def test_satisfies_force_model_protocol(self) -> None:
        assert isinstance(default_force_system(BALL, ENV), ForceModel)
        assert isinstance(Gravity(ENV), ForceModel)

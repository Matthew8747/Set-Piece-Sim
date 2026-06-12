"""Force models acting on the ball, expressed as accelerations.

Each force is a small class that precomputes its constants from config and
exposes a broadcast-polymorphic ``acceleration(position, velocity, spin)``
kernel (see ``restart.simulation.interfaces.ForceModel``). Composition is a
plain sum (``ForceSystem``) — forces are independent and additive in this
regime.

Assumption IDs (P-*) refer to docs/simulation-assumptions.md.
"""

from collections.abc import Sequence

import numpy as np

from restart.domain.vectors import FloatArray, cross, norm, unit
from restart.physics.config import BallConfig, EnvironmentConfig
from restart.simulation.interfaces import ForceModel


class Gravity:
    """Uniform gravity, -z (P-2)."""

    name = "gravity"

    def __init__(self, environment: EnvironmentConfig) -> None:
        self._g = environment.gravity_ms2

    def acceleration(
        self, position: FloatArray, velocity: FloatArray, spin: FloatArray
    ) -> FloatArray:
        a = np.zeros_like(velocity)
        a[..., 2] = -self._g
        return a


class QuadraticDrag:
    """Quadratic aerodynamic drag with a smooth drag crisis (P-3).

    a = -(rho*A / 2m) * C_d(|v|) * |v| * v

    C_d(|v|) blends logistically from cd_subcritical (slow, laminar-dominated)
    to cd_supercritical (fast, post-crisis) around v_critical_ms. The smooth
    blend is a deliberate idealization of the experimentally sharp transition:
    it keeps the ODE C^1 (kind to the integrator) and we never operate exactly
    at the cliff edge.
    """

    name = "drag"

    def __init__(self, ball: BallConfig, environment: EnvironmentConfig) -> None:
        self._k = 0.5 * environment.air_density_kgm3 * ball.cross_section_m2 / ball.mass_kg
        d = ball.drag
        self._cd_low_speed = d.cd_subcritical
        self._cd_high_speed = d.cd_supercritical
        self._v_crit = d.v_critical_ms
        self._width = d.transition_width_ms

    def drag_coefficient(self, speed: FloatArray) -> FloatArray:
        """C_d as a function of speed (exposed for validation plots/tests)."""
        # Logistic blend: sigma -> 0 at low speed, -> 1 well above v_crit.
        sigma = 1.0 / (1.0 + np.exp(-(speed - self._v_crit) / self._width))
        result: FloatArray = self._cd_low_speed + (self._cd_high_speed - self._cd_low_speed) * sigma
        return result

    def acceleration(
        self, position: FloatArray, velocity: FloatArray, spin: FloatArray
    ) -> FloatArray:
        speed = norm(velocity)
        cd = self.drag_coefficient(speed)
        return -self._k * (cd * speed)[..., np.newaxis] * velocity


class MagnusLift:
    """Magnus (lift) force from spin (P-4).

    a = (rho*A / 2m) * C_l * |v|^2 * unit(spin x velocity)

    with C_l = S / (a*S + b), spin parameter S = r*|spin| / |v| clamped to
    spin_parameter_max. unit() maps the zero vector to zero, so the force
    vanishes smoothly when spin is zero or parallel to velocity.
    """

    name = "magnus"

    def __init__(self, ball: BallConfig, environment: EnvironmentConfig) -> None:
        self._k = 0.5 * environment.air_density_kgm3 * ball.cross_section_m2 / ball.mass_kg
        self._r = ball.radius_m
        m = ball.magnus
        self._a = m.coeff_a
        self._b = m.coeff_b
        self._s_max = m.spin_parameter_max

    def lift_coefficient(self, speed: FloatArray, spin_rate: FloatArray) -> FloatArray:
        """C_l from speed and spin magnitude (exposed for validation)."""
        s = self._r * spin_rate / np.maximum(speed, 1e-9)
        s = np.minimum(s, self._s_max)
        result: FloatArray = s / (self._a * s + self._b)
        return result

    def acceleration(
        self, position: FloatArray, velocity: FloatArray, spin: FloatArray
    ) -> FloatArray:
        speed = norm(velocity)
        cl = self.lift_coefficient(speed, norm(spin))
        direction = unit(cross(spin, velocity))
        return self._k * (cl * speed * speed)[..., np.newaxis] * direction


class ForceSystem:
    """Additive composition of force models; itself a ForceModel."""

    def __init__(self, forces: Sequence[ForceModel]) -> None:
        if not forces:
            msg = "ForceSystem requires at least one force"
            raise ValueError(msg)
        self._forces = tuple(forces)

    @property
    def name(self) -> str:
        return "+".join(f.name for f in self._forces)

    @property
    def forces(self) -> tuple[ForceModel, ...]:
        return self._forces

    def acceleration(
        self, position: FloatArray, velocity: FloatArray, spin: FloatArray
    ) -> FloatArray:
        total = self._forces[0].acceleration(position, velocity, spin)
        for f in self._forces[1:]:
            total = total + f.acceleration(position, velocity, spin)
        return total


def default_force_system(ball: BallConfig, environment: EnvironmentConfig) -> ForceSystem:
    """The standard flight model: gravity + drag + Magnus."""
    return ForceSystem(
        [
            Gravity(environment),
            QuadraticDrag(ball, environment),
            MagnusLift(ball, environment),
        ]
    )

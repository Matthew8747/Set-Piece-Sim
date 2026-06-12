"""Closed-form reference solutions for the validation framework.

These are *oracles*, not production code: exact answers for special cases the
integrator must reproduce. The third oracle (SciPy DOP853 on the full force
model) lives in the test suite, since it needs no new physics.
"""

import math

import numpy as np

from restart.domain.vectors import FloatArray
from restart.physics.config import BallConfig, EnvironmentConfig


def drag_free_position(
    position0: FloatArray, velocity0: FloatArray, gravity_ms2: float, times_s: FloatArray
) -> FloatArray:
    """Ballistic trajectory without air: r(t) = r0 + v0 t - (g t^2 / 2) z.

    ``times_s`` shape ``(n,)`` -> result shape ``(n, 3)``.
    """
    t = times_s[:, np.newaxis]
    out = position0[np.newaxis, :] + velocity0[np.newaxis, :] * t
    out[:, 2] -= 0.5 * gravity_ms2 * times_s**2
    return out


def drag_free_apex(z0: float, vz0: float, gravity_ms2: float) -> tuple[float, float]:
    """(time, height) of the apex for a drag-free launch with vz0 > 0."""
    if vz0 <= 0.0:
        msg = f"apex requires upward launch, got vz0={vz0}"
        raise ValueError(msg)
    t = vz0 / gravity_ms2
    return t, z0 + vz0 * t - 0.5 * gravity_ms2 * t * t


def terminal_speed(
    ball: BallConfig, environment: EnvironmentConfig, drag_coefficient: float
) -> float:
    """Speed at which quadratic drag balances gravity for a falling ball:
    v_t = sqrt(2 m g / (rho A C_d)).
    """
    return math.sqrt(
        2.0
        * ball.mass_kg
        * environment.gravity_ms2
        / (environment.air_density_kgm3 * ball.cross_section_m2 * drag_coefficient)
    )

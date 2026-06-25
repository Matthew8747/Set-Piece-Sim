"""Ground-bounce impulse model (P-7, P-8, P-9).

Sphere on horizontal plane, instantaneous impulse:

* Normal: v_z' = -e * v_z (restitution e).
* Tangential: Coulomb friction impulse opposing the **contact-point slip**
  (which couples velocity and spin), with the standard stick/slide branch:
  if the friction impulse needed to stop the slip is within mu * J_normal,
  the contact sticks and the ball leaves the bounce rolling-compatible;
  otherwise it slides and takes the full Coulomb impulse.
* Spin about the normal (z) is unchanged: no twisting-friction model (P-9
  simplification, registered).

Derivation sketch (per unit mass; n = (0,0,1), r = ball radius,
beta = I/(m r^2)):

    contact-point velocity  u   = v - r * (w x n)         (horizontal slip)
    normal impulse          j_n = (1 + e) * |v_z|
    slip change per unit tangential impulse = (1 + 1/beta)
    impulse to stick        j_stick = |u| / (1 + 1/beta)
    tangential impulse      j_t = min(mu * j_n, j_stick)  opposing slip
    dv = -j_t * unit(u);    dw = -(1/(beta r)) * n x dv
"""

import numpy as np

from restart.domain.vectors import FloatArray, vec3
from restart.physics.config import BallConfig, BounceConfig

_Z = vec3(0.0, 0.0, 1.0)


def bounce(
    velocity: FloatArray,
    spin: FloatArray,
    bounce_cfg: BounceConfig,
    ball: BallConfig,
) -> tuple[FloatArray, FloatArray]:
    """Resolve one ground bounce. Returns (velocity', spin'); inputs unchanged.

    Single-state kernel ``(3,)`` - bounces are resolved per-trajectory in
    Phase 1; the batch variant lands with the Monte Carlo layer (ADR-002 d4).
    """
    v = np.asarray(velocity, dtype=np.float64).copy()
    w = np.asarray(spin, dtype=np.float64).copy()
    if v[2] >= 0.0:
        msg = f"bounce requires downward motion, got v_z={v[2]}"
        raise ValueError(msg)

    e = bounce_cfg.restitution
    mu = bounce_cfg.friction_mu
    r = ball.radius_m
    beta = ball.moi_factor

    j_n = (1.0 + e) * (-v[2])  # normal impulse per unit mass (> 0)

    # Horizontal slip of the contact point: u = v - r*(w x n), z comp is v_z.
    w_cross_n = np.cross(w, _Z)
    u = v - r * w_cross_n
    u[2] = 0.0
    slip = float(np.linalg.norm(u))

    if slip > 1e-12:
        slip_dir = u / slip
        j_stick = slip / (1.0 + 1.0 / beta)
        j_t = min(mu * j_n, j_stick)
        dv = -j_t * slip_dir
        v = v + dv
        # dw = -(1/(beta r)) * n x dv
        w = w - (1.0 / (beta * r)) * np.cross(_Z, dv)

    v[2] = e * (-v[2])
    return v, w


def total_kinetic_energy(velocity: FloatArray, spin: FloatArray, ball: BallConfig) -> float:
    """Translational + rotational kinetic energy (J).

    The conserved-or-dissipated quantity across a bounce. Translational KE
    alone can legitimately *increase* (strong backspin converts rotational
    energy into horizontal velocity - the classic spin-back); the total never
    does, which is the invariant the property tests pin.
    """
    m = ball.mass_kg
    i = ball.moment_of_inertia
    return 0.5 * m * float(np.dot(velocity, velocity)) + 0.5 * i * float(np.dot(spin, spin))


def energy_retained(
    v_in: FloatArray,
    w_in: FloatArray,
    v_out: FloatArray,
    w_out: FloatArray,
    ball: BallConfig,
) -> float:
    """Fraction of total kinetic energy retained across a bounce, in (0, 1]."""
    e_in = total_kinetic_energy(v_in, w_in, ball)
    e_out = total_kinetic_energy(v_out, w_out, ball)
    return e_out / e_in if e_in > 0.0 else 1.0

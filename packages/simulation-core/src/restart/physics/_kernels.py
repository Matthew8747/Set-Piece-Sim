"""Fused JIT flight kernel - the production batch path (ADR-001 addendum).

Implements gravity + drag-crisis drag + Magnus + spin decay + RK4 + ground-
crossing detection in one pass per simulation, eliminating the NumPy path's
per-step temporary allocations (measured 6.8 s -> sub-second for 10k flights).

EQUIVALENCE CONTRACT: this kernel must reproduce
``restart.physics.batch._simulate_flights_numpy`` (the readable reference)
to <= 1e-9 absolute; ``tests/test_batch.py`` enforces it. Formulas and guard
epsilons are copied *verbatim in semantics* from ``forces.py`` - change both
together or the equivalence test will catch you.

Typing note: ``numba.njit`` is untyped; the ``TYPE_CHECKING`` split lets mypy
check the plain functions while runtime gets the compiled versions.
"""

import math
from typing import TYPE_CHECKING

import numpy as np

from restart.domain.vectors import FloatArray

if TYPE_CHECKING:
    BoolArray = np.typing.NDArray[np.bool_]


def _derivative_into(
    y: FloatArray,
    out: FloatArray,
    g: float,
    k_aero: float,
    cd_sub: float,
    cd_super: float,
    v_crit: float,
    width: float,
    r_ball: float,
    mag_a: float,
    mag_b: float,
    s_max: float,
    tau: float,
) -> None:
    vx, vy, vz = y[3], y[4], y[5]
    wx, wy, wz = y[6], y[7], y[8]

    out[0] = vx
    out[1] = vy
    out[2] = vz

    ax = 0.0
    ay = 0.0
    az = -g

    speed = math.sqrt(vx * vx + vy * vy + vz * vz)

    # Drag with logistic drag crisis (mirrors QuadraticDrag).
    sigma = 1.0 / (1.0 + math.exp(-(speed - v_crit) / width))
    cd = cd_sub + (cd_super - cd_sub) * sigma
    kd = k_aero * cd * speed
    ax -= kd * vx
    ay -= kd * vy
    az -= kd * vz

    # Magnus (mirrors MagnusLift, including both guard epsilons).
    wmag = math.sqrt(wx * wx + wy * wy + wz * wz)
    s = r_ball * wmag / max(speed, 1e-9)
    if s > s_max:
        s = s_max
    cl = s / (mag_a * s + mag_b)
    cx = wy * vz - wz * vy
    cy = wz * vx - wx * vz
    cz = wx * vy - wy * vx
    cn = math.sqrt(cx * cx + cy * cy + cz * cz)
    km = k_aero * cl * speed * speed / max(cn, 1e-12)
    ax += km * cx
    ay += km * cy
    az += km * cz

    out[3] = ax
    out[4] = ay
    out[5] = az

    out[6] = -wx / tau
    out[7] = -wy / tau
    out[8] = -wz / tau


def _flight_batch(
    y0: FloatArray,
    dt: float,
    n_steps: int,
    ground_z: float,
    g: float,
    k_aero: float,
    cd_sub: float,
    cd_super: float,
    v_crit: float,
    width: float,
    r_ball: float,
    mag_a: float,
    mag_b: float,
    s_max: float,
    tau: float,
) -> tuple[FloatArray, FloatArray, FloatArray, "BoolArray"]:
    n = y0.shape[0]
    landing_y = np.full((n, 9), np.nan)
    landing_t = np.full(n, np.nan)
    apex = np.empty(n)
    landed = np.zeros(n, dtype=np.bool_)

    y = np.empty(9)
    y_new = np.empty(9)
    yt = np.empty(9)
    k1 = np.empty(9)
    k2 = np.empty(9)
    k3 = np.empty(9)
    k4 = np.empty(9)

    for i in range(n):
        for j in range(9):
            y[j] = y0[i, j]
        apex_i = y[2]
        t = 0.0

        for _ in range(n_steps):
            _derivative_into(
                y, k1, g, k_aero, cd_sub, cd_super, v_crit, width, r_ball, mag_a, mag_b, s_max, tau
            )
            for j in range(9):
                yt[j] = y[j] + (0.5 * dt) * k1[j]
            _derivative_into(
                yt, k2, g, k_aero, cd_sub, cd_super, v_crit, width, r_ball, mag_a, mag_b, s_max, tau
            )
            for j in range(9):
                yt[j] = y[j] + (0.5 * dt) * k2[j]
            _derivative_into(
                yt, k3, g, k_aero, cd_sub, cd_super, v_crit, width, r_ball, mag_a, mag_b, s_max, tau
            )
            for j in range(9):
                yt[j] = y[j] + dt * k3[j]
            _derivative_into(
                yt, k4, g, k_aero, cd_sub, cd_super, v_crit, width, r_ball, mag_a, mag_b, s_max, tau
            )
            for j in range(9):
                y_new[j] = y[j] + (dt / 6.0) * (k1[j] + 2.0 * k2[j] + 2.0 * k3[j] + k4[j])

            if y[2] >= ground_z and y_new[2] < ground_z and y_new[5] < 0.0:
                frac = (y[2] - ground_z) / (y[2] - y_new[2])
                for j in range(9):
                    landing_y[i, j] = y[j] + frac * (y_new[j] - y[j])
                landing_y[i, 2] = ground_z
                landing_t[i] = t + frac * dt
                landed[i] = True
                break

            if y_new[2] > apex_i:
                apex_i = y_new[2]
            for j in range(9):
                y[j] = y_new[j]
            t = t + dt

        apex[i] = apex_i

    return landing_y, landing_t, apex, landed


if TYPE_CHECKING:
    flight_batch = _flight_batch
else:  # pragma: no cover - decoration, not logic
    from numba import njit

    _derivative_into = njit(cache=True, fastmath=False)(_derivative_into)
    flight_batch = njit(cache=True, fastmath=False)(_flight_batch)

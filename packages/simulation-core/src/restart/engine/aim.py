"""Delivery aim solver: what launch actually puts the ball on the target.

The engine used to aim with the drag-free range equation and a single fudge
factor (``carry_factor``) standing in for drag. Measured against the real flight
model that heuristic is not close:

* the true carry ratio is not a constant - it runs from 0.85 at 18 m/s down to
  0.72 at 32 m/s, because faster balls spend longer in the high-drag regime;
* the range equation's low root is the wrong branch. Optimal corner elevations
  are 39-56 degrees, and the old ``elev_max_deg`` cap of 35 clipped three of the
  five stock routines before they could even be considered;
* Magnus curl is far larger than the linear pre-aim allowed for. At 8 rev/s the
  ball bends ~6.2 m over a 31 m flight; the old compensation corrected ~3.5 m.

Net effect: stock corners landed 3.3-6.8 m from their nominal target, drifted
across the goal line, and 34-65% of deliveries went straight out of play. Every
routine collapsed to the same "ball never arrives" behaviour, which is why
routines did not diverge from one another.

So aim numerically instead. Search launch (speed, elevation, heading) whose
*arrival point* under the real gravity+drag+Magnus model is the routine's
delivery target, using the same fused kernel the batch path uses.

"Arrival" is where the ball descends through heading height, not where it lands.
That distinction decides who gets to the ball first. Aiming the landing point
put the ball into contact range about 5 m before the runner's mark - measured on
the near-post inswinger, contact happened at y = -7.9 while the ball landed at
y = -2.5 - so the delivery was always cut out by whichever defender already
stood in that space, and attackers won only 2-15% of first contacts. A delivery
that never climbs to heading height (a short corner) falls back to its landing
point, the only arrival it has.

The solve is deterministic and depends only on scalars, so it is cached and
costs nothing per simulation - see ``solve_aim``.
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

from restart.domain import pitch
from restart.domain.vectors import FloatArray
from restart.physics import _kernels
from restart.physics.config import PhysicsConfig

# Launch height of a struck dead ball (matches the engine's kick state).
_LAUNCH_Z = 0.11
# The solver only ever needs the delivery arc, never the roll-out.
_SOLVE_HORIZON_S = 6.0


def _best(
    kick_xy: tuple[float, float],
    target_xy: tuple[float, float],
    speed: float,
    elevs: FloatArray,
    headings: FloatArray,
    spin_signed_rps: float,
    contact_height_m: float,
    physics: PhysicsConfig,
) -> tuple[float, float, float]:
    """Best (error, elevation, heading) over the ``elevs`` x ``headings`` grid.

    Candidates whose flight leaves the field of play are infeasible, not merely
    poor: without that constraint the search "reaches" a far-post target by
    firing the ball over the goal line 0.3 m from the corner flag, because the
    landing point beyond the line still scores well.
    """
    ee, hh = np.meshgrid(elevs, headings, indexing="ij")
    e = ee.ravel()
    h = hh.ravel()
    y0 = np.zeros((e.size, 9))
    y0[:, 0] = kick_xy[0]
    y0[:, 1] = kick_xy[1]
    y0[:, 2] = _LAUNCH_Z
    y0[:, 3] = speed * np.cos(e) * np.cos(h)
    y0[:, 4] = speed * np.cos(e) * np.sin(h)
    y0[:, 5] = speed * np.sin(e)
    y0[:, 8] = spin_signed_rps * 2.0 * math.pi

    ball, env = physics.ball, physics.environment
    landing_xy, ok = _kernels.aim_probe(
        np.ascontiguousarray(y0),
        physics.integrator.dt_s,
        int(np.ceil(_SOLVE_HORIZON_S / physics.integrator.dt_s)),
        ball.radius_m,
        pitch.HALF_LENGTH_M,
        pitch.HALF_WIDTH_M,
        contact_height_m,
        env.gravity_ms2,
        0.5 * env.air_density_kgm3 * ball.cross_section_m2 / ball.mass_kg,
        ball.drag.cd_subcritical,
        ball.drag.cd_supercritical,
        ball.drag.v_critical_ms,
        ball.drag.transition_width_ms,
        ball.radius_m,
        ball.magnus.coeff_a,
        ball.magnus.coeff_b,
        ball.magnus.spin_parameter_max,
        ball.spin_decay_tau_s,
    )
    err = np.where(
        ok, np.hypot(landing_xy[:, 0] - target_xy[0], landing_xy[:, 1] - target_xy[1]), np.inf
    )
    k = int(np.argmin(err))
    return float(err[k]), float(e[k]), float(h[k])


@lru_cache(maxsize=512)
def solve_aim(
    kick_x: float,
    kick_y: float,
    target_x: float,
    target_y: float,
    nominal_speed_ms: float,
    spin_signed_rps: float,
    elev_min_deg: float,
    elev_max_deg: float,
    max_speed_ms: float,
    tolerance_m: float,
    contact_height_m: float,
    physics: PhysicsConfig,
) -> tuple[float, float, float]:
    """Return the launch ``(speed_ms, elevation_rad, heading_rad)`` that lands on target.

    Deterministic and side-effect free: identical arguments always return the
    identical triple, so compiling the same scenario twice cannot drift. Cached
    because the result depends only on these scalars - a Monte Carlo batch of
    2000 sims solves once, not 2000 times.

    Speed is escalated only when it has to be. A taker who cannot reach the
    target with the routine's nominal weight hits it harder, so the solver walks
    a speed ladder upward and stops at the first rung that lands within
    ``tolerance_m``; if no rung reaches, it returns the closest attempt at the
    top of the ladder rather than silently aiming somewhere else.
    """
    kick_xy = (kick_x, kick_y)
    target_xy = (target_x, target_y)
    base = math.atan2(target_y - kick_y, target_x - kick_x)

    # Spin bends the flight, so the heading window must be wide enough to hold
    # the pre-aim: 8 rev/s needs ~22 degrees of it.
    coarse_elev = np.radians(np.linspace(elev_min_deg, elev_max_deg, 24))
    coarse_off = np.radians(np.linspace(-32.0, 32.0, 33))

    speeds = [nominal_speed_ms]
    s = nominal_speed_ms + 1.0
    while s <= max_speed_ms + 1e-9:
        speeds.append(round(s, 6))
        s += 1.0

    # Seeded with a plausible lofted delivery on the nominal line, not a 0 rad
    # scud: if no candidate were ever feasible this seed is what gets returned,
    # and a flat drive along the goal line is a much worse thing to fall back to
    # than an ordinary hanging cross.
    best: tuple[float, float, float, float] = (
        math.inf,
        math.radians(0.5 * (elev_min_deg + elev_max_deg)),
        base,
        nominal_speed_ms,
    )
    for speed in speeds:
        err, elev, head = _best(
            kick_xy,
            target_xy,
            speed,
            coarse_elev,
            base + coarse_off,
            spin_signed_rps,
            contact_height_m,
            physics,
        )
        if err < best[0]:
            best = (err, elev, head, speed)
        if err <= max(tolerance_m * 4.0, 1.5):
            break  # this rung is close enough that refinement will finish the job

    _, elev0, head0, speed0 = best

    # Two local refinements around the coarse winner. The landing point is
    # smooth in (elevation, heading), so bisection-by-grid converges fast.
    span_e, span_h = math.radians(4.0), math.radians(4.0)
    for _ in range(2):
        fine_elev = np.clip(
            np.linspace(elev0 - span_e, elev0 + span_e, 17),
            math.radians(elev_min_deg),
            math.radians(elev_max_deg),
        )
        fine_head = np.linspace(head0 - span_h, head0 + span_h, 17)
        err, elev0, head0 = _best(
            kick_xy,
            target_xy,
            speed0,
            fine_elev,
            fine_head,
            spin_signed_rps,
            contact_height_m,
            physics,
        )
        span_e *= 0.25
        span_h *= 0.25

    return speed0, elev0, head0

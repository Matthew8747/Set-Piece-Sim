"""Scalar-loop njit ports of the agent kinematics kernels (ADR-011, Phase 10).

EQUIVALENCE CONTRACT: each function here must reproduce its broadcast NumPy
reference in ``agents/kinematics.py`` to <= 1e-9 absolute; ``tests/
test_agents_kernels.py`` enforces it. Formulas and guard epsilons are copied
*verbatim in semantics* from kinematics.py - change both together or the
equivalence test will catch you.

These are the per-tick hot path the fused scenario kernel (Phase 10) calls with
no Python in the loop. Same TYPE_CHECKING split as physics/_kernels.py: mypy
checks the plain functions; runtime gets the njit-compiled versions.
"""

import math
from typing import TYPE_CHECKING

import numpy as np

from restart.domain.vectors import FloatArray

_EPS = 1e-12


def _step_agents_kernel(
    pos: FloatArray,
    vel: FloatArray,
    targets: FloatArray,
    top_speed: FloatArray,
    accel: FloatArray,
    agility: FloatArray,
    dt: float,
    turn_rate_base: float,
    speed_ref: float,
    arrival_radius: float,
) -> tuple[FloatArray, FloatArray]:
    """Scalar port of kinematics.step_agents (semi-implicit Euler, G-1)."""
    n = pos.shape[0]
    pos_new = np.empty((n, 2))
    vel_new = np.empty((n, 2))
    two_pi = 2.0 * math.pi

    for i in range(n):
        dx = targets[i, 0] - pos[i, 0]
        dy = targets[i, 1] - pos[i, 1]
        dist = math.sqrt(dx * dx + dy * dy)
        arrived = dist <= arrival_radius

        # Unit vector toward target; zero for arrived agents.
        if arrived:
            ux = 0.0
            uy = 0.0
        else:
            ux = dx / dist
            uy = dy / dist

        ts = top_speed[i]
        desired_x = ux * ts
        desired_y = uy * ts

        # Velocity update clamped to accel*dt.
        dvx = desired_x - vel[i, 0]
        dvy = desired_y - vel[i, 1]
        dv_mag = math.sqrt(dvx * dvx + dvy * dvy)
        max_dv = accel[i] * dt
        denom = dv_mag if dv_mag > _EPS else _EPS
        scale = min(1.0, max_dv / denom)
        vnx = vel[i, 0] + dvx * scale
        vny = vel[i, 1] + dvy * scale

        speed_old = math.sqrt(vel[i, 0] * vel[i, 0] + vel[i, 1] * vel[i, 1])
        speed_new = math.sqrt(vnx * vnx + vny * vny)
        can_turn_free = speed_old <= 0.5

        if not can_turn_free:
            agility_factor = 0.25 + 0.75 * agility[i]
            speed_taper = speed_ref / (speed_old + speed_ref)
            max_turn = dt * turn_rate_base * agility_factor * speed_taper

            heading_old = math.atan2(vel[i, 1], vel[i, 0])
            heading_new = math.atan2(vny, vnx)
            delta = heading_new - heading_old
            delta = (delta + math.pi) % two_pi - math.pi
            # clip(delta, -max_turn, max_turn)
            if delta < -max_turn:
                clamped_delta = -max_turn
            elif delta > max_turn:
                clamped_delta = max_turn
            else:
                clamped_delta = delta
            clamped_heading = heading_old + clamped_delta
            vnx = math.cos(clamped_heading) * speed_new
            vny = math.sin(clamped_heading) * speed_new

        # Final speed clamp.
        speed_final = math.sqrt(vnx * vnx + vny * vny)
        if speed_final > ts:
            sden = speed_final if speed_final > _EPS else _EPS
            safe_speed = ts / sden
            vnx *= safe_speed
            vny *= safe_speed

        vel_new[i, 0] = vnx
        vel_new[i, 1] = vny
        pos_new[i, 0] = pos[i, 0] + vnx * dt
        pos_new[i, 1] = pos[i, 1] + vny * dt

    return pos_new, vel_new


def _time_to_point_kernel(
    pos: FloatArray,
    vel: FloatArray,
    target: FloatArray,
    top_speed: FloatArray,
    accel: FloatArray,
) -> FloatArray:
    """Scalar port of kinematics.time_to_point (accel-then-cruise, G-1).

    ``target`` is (n, 2): one target per agent (the interception caller tiles
    ball samples into this shape).
    """
    n = pos.shape[0]
    out = np.empty(n)

    for i in range(n):
        dx = target[i, 0] - pos[i, 0]
        dy = target[i, 1] - pos[i, 1]
        dist = math.sqrt(dx * dx + dy * dy)
        safe_dist = dist if dist > _EPS else _EPS
        ux = dx / safe_dist
        uy = dy / safe_dist

        v0 = vel[i, 0] * ux + vel[i, 1] * uy
        ts = top_speed[i]
        # clip(v0, 0.0, top_speed)
        if v0 < 0.0:
            v0 = 0.0
        elif v0 > ts:
            v0 = ts

        at_target = dist <= _EPS
        safe_accel = accel[i] if accel[i] > _EPS else _EPS

        t_accel = (ts - v0) / safe_accel
        d_accel = v0 * t_accel + 0.5 * safe_accel * t_accel * t_accel

        disc = v0 * v0 + 2.0 * safe_accel * dist
        disc = disc if disc > 0.0 else 0.0
        t_accel_only = (-v0 + math.sqrt(disc)) / safe_accel

        ts_den = ts if ts > _EPS else _EPS
        d_cruise = dist - d_accel
        t_cruise = d_cruise / ts_den
        t_both = t_accel + t_cruise

        t_raw = t_accel_only if d_accel >= dist else t_both
        out[i] = 0.0 if at_target else t_raw

    return out


def _earliest_interception_kernel(
    pos: FloatArray,
    vel: FloatArray,
    top_speed: FloatArray,
    accel: FloatArray,
    reach: FloatArray,
    ready_time: FloatArray,
    ball_times: FloatArray,
    ball_pos: FloatArray,
) -> "np.ndarray":
    """Scalar port of interception.earliest_interception (G-3).

    Returns the earliest interceptable ball-sample index per agent, or -1. The
    travel-time test inlines time_to_point's accel-then-cruise formula verbatim,
    so the feasibility decision matches the NumPy reference bit-for-bit.
    """
    n = pos.shape[0]
    m = ball_times.shape[0]
    result = np.full(n, -1, dtype=np.int64)

    for i in range(n):
        ts = top_speed[i]
        ts_den = ts if ts > _EPS else _EPS
        safe_accel = accel[i] if accel[i] > _EPS else _EPS
        for k in range(m):
            # Reaction gate, then reach gate (cheapest first; same mask as ref).
            if ready_time[i] > ball_times[k]:
                continue
            if reach[i] < ball_pos[k, 2]:
                continue
            # Travel-time gate (inline time_to_point).
            dx = ball_pos[k, 0] - pos[i, 0]
            dy = ball_pos[k, 1] - pos[i, 1]
            dist = math.sqrt(dx * dx + dy * dy)
            safe_dist = dist if dist > _EPS else _EPS
            ux = dx / safe_dist
            uy = dy / safe_dist
            v0 = vel[i, 0] * ux + vel[i, 1] * uy
            if v0 < 0.0:
                v0 = 0.0
            elif v0 > ts:
                v0 = ts
            t_accel = (ts - v0) / safe_accel
            d_accel = v0 * t_accel + 0.5 * safe_accel * t_accel * t_accel
            disc = v0 * v0 + 2.0 * safe_accel * dist
            disc = disc if disc > 0.0 else 0.0
            t_accel_only = (-v0 + math.sqrt(disc)) / safe_accel
            d_cruise = dist - d_accel
            t_cruise = d_cruise / ts_den
            t_both = t_accel + t_cruise
            t_raw = t_accel_only if d_accel >= dist else t_both
            travel = 0.0 if dist <= _EPS else t_raw

            if travel <= ball_times[k]:
                result[i] = k
                break

    return result


def _separate_kernel(pos: FloatArray, radius: float, passes: int) -> FloatArray:
    """Scalar port of kinematics.separate (soft-disc separation, G-7).

    Faithful to the reference's ordering: degenerate agents are detected from the
    *original* positions (never the partially-relocated copy), and each cleanup
    pass selects its overlapping pair set from the *pass-start* snapshot while
    pushing with *live* distances - so the float sequence matches to <=1e-9.
    """
    n = pos.shape[0]
    pos_out = pos.copy()
    min_dist = 2.0 * radius
    tiny = 1e-6
    md2 = min_dist * min_dist
    tiny2 = tiny * tiny

    # Earliest exit: nobody overlapping (the common per-tick case).
    min_d2 = np.inf
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dx = pos_out[i, 0] - pos_out[j, 0]
            dy = pos_out[i, 1] - pos_out[j, 1]
            d2 = dx * dx + dy * dy
            if d2 < min_d2:
                min_d2 = d2
    if min_d2 >= md2:
        return pos_out

    # Grid-seed degenerate clusters (only when near-coincident agents exist).
    # Detection uses the ORIGINAL positions so early relocations don't un-mark
    # later agents still sitting on the pile.
    # Integer ceil(sqrt(n)) - matches np.ceil(np.sqrt(n)) at these arities while
    # staying pure-int (numba's math.ceil returns a float; this avoids the cast).
    floor_sqrt = int(math.sqrt(n))
    cols = floor_sqrt if floor_sqrt * floor_sqrt >= n else floor_sqrt + 1
    grid_spacing = min_dist * 1.05
    cx = 0.0
    cy = 0.0
    for i in range(n):
        cx += pos[i, 0]
        cy += pos[i, 1]
    cx /= n
    cy /= n
    if min_d2 < tiny2:
        for i in range(n):
            degenerate = False
            for j in range(n):
                if i == j:
                    continue
                dx = pos[i, 0] - pos[j, 0]
                dy = pos[i, 1] - pos[j, 1]
                if dx * dx + dy * dy < tiny2:
                    degenerate = True
                    break
            if degenerate:
                row = i // cols
                col = i % cols
                pos_out[i, 0] = cx + (col - (cols - 1) / 2.0) * grid_spacing
                pos_out[i, 1] = cy + (row - (cols - 1) / 2.0) * grid_spacing

    # Cleanup sweeps over the overlapping pairs (i < j, ascending = triu order).
    snap = np.empty((n, 2))
    for _ in range(passes):
        for i in range(n):
            snap[i, 0] = pos_out[i, 0]
            snap[i, 1] = pos_out[i, 1]
        any_pair = False
        for i in range(n):
            for j in range(i + 1, n):
                sdx = snap[j, 0] - snap[i, 0]
                sdy = snap[j, 1] - snap[i, 1]
                if sdx * sdx + sdy * sdy < md2:
                    any_pair = True
                    dx = pos_out[j, 0] - pos_out[i, 0]
                    dy = pos_out[j, 1] - pos_out[i, 1]
                    d = math.sqrt(dx * dx + dy * dy)
                    if d >= min_dist:
                        continue
                    overlap = min_dist - d
                    if d < tiny:
                        ax = 1.0
                        ay = 0.0
                    else:
                        ax = dx / d
                        ay = dy / d
                    push_x = 0.5 * overlap * ax
                    push_y = 0.5 * overlap * ay
                    pos_out[i, 0] -= push_x
                    pos_out[i, 1] -= push_y
                    pos_out[j, 0] += push_x
                    pos_out[j, 1] += push_y
        if not any_pair:
            break

    return pos_out


if TYPE_CHECKING:
    step_agents_kernel = _step_agents_kernel
    time_to_point_kernel = _time_to_point_kernel
    earliest_interception_kernel = _earliest_interception_kernel
    separate_kernel = _separate_kernel
else:  # pragma: no cover - decoration, not logic
    from numba import njit

    step_agents_kernel = njit(cache=True, fastmath=False)(_step_agents_kernel)
    time_to_point_kernel = njit(cache=True, fastmath=False)(_time_to_point_kernel)
    earliest_interception_kernel = njit(cache=True, fastmath=False)(_earliest_interception_kernel)
    separate_kernel = njit(cache=True, fastmath=False)(_separate_kernel)

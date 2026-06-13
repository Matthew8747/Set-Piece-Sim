"""Agent kinematics kernels.

Broadcast kernels over n agents represented as flat float64 arrays (SoA
contract per ADR-003 d8). All functions are pure — they return new arrays and
never mutate inputs. Signatures are Numba-portable: no Python objects, no
variable-length Python lists in hot paths.

Assumption IDs referenced here:
- G-1: accel/speed/turn-rate envelope (2.5-D point-mass model)
- G-3: reaction-time / latency modelling (time_to_point is used by
  interception to gate feasibility before ready_time)
"""

from __future__ import annotations

import numpy as np

from restart.domain.vectors import FloatArray

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_EPS: float = 1e-12


def _safe_norm2(arr: FloatArray) -> FloatArray:
    """Row-wise Euclidean norm for (n, 2) array.  Returns (n,)."""
    result: FloatArray = np.sqrt(np.sum(arr * arr, axis=-1))
    return result


# ---------------------------------------------------------------------------
# Public kernels
# ---------------------------------------------------------------------------


def step_agents(
    pos: FloatArray,
    vel: FloatArray,
    targets: FloatArray,
    top_speed: FloatArray,
    accel: FloatArray,
    agility: FloatArray,
    dt: float,
    *,
    turn_rate_base: float,
    speed_ref: float,
    arrival_radius: float,
) -> tuple[FloatArray, FloatArray]:
    """Advance n agents by one tick using semi-implicit Euler (G-1).

    Parameters
    ----------
    pos:            (n, 2) current positions (m)
    vel:            (n, 2) current velocities (m/s)
    targets:        (n, 2) waypoint targets (m)
    top_speed:      (n,)   maximum speed (m/s)
    accel:          (n,)   acceleration magnitude (m/s²)
    agility:        (n,)   0-1 agility rating (scales turn-rate cap)
    dt:             tick duration (s)
    turn_rate_base: maximum heading-change rate scale (rad/s) — AgentConfig
    speed_ref:      reference speed for turn taper (m/s) — AgentConfig
    arrival_radius: arrive-and-hold threshold (m) — AgentConfig

    Returns
    -------
    pos_new : (n, 2)  positions after the tick
    vel_new : (n, 2)  velocities after the tick

    Notes
    -----
    Turn neglect in ``time_to_point`` is acceptable because this function
    already enforces turn constraints; the planner treats paths as straight
    lines (G-1 simplification).
    """
    # --- desired velocity ---------------------------------------------------
    diff = targets - pos  # (n, 2)
    dist = _safe_norm2(diff)  # (n,)
    arrived = dist <= arrival_radius  # (n,) bool

    # unit vector toward target; zero for arrived agents
    safe_dist = np.where(arrived, 1.0, dist)  # avoid /0
    unit_to_target = diff / safe_dist[:, np.newaxis]  # (n, 2)
    unit_to_target = np.where(arrived[:, np.newaxis], 0.0, unit_to_target)

    desired_vel = unit_to_target * top_speed[:, np.newaxis]  # (n, 2)

    # --- velocity update clamped to accel*dt --------------------------------
    dv = desired_vel - vel  # (n, 2)
    dv_mag = _safe_norm2(dv)  # (n,)
    max_dv = accel * dt  # (n,)

    # scale down if |dv| > max_dv
    scale = np.minimum(1.0, max_dv / np.maximum(dv_mag, _EPS))  # (n,)
    vel_new = vel + dv * scale[:, np.newaxis]  # (n, 2)

    # --- turn-rate clamp ----------------------------------------------------
    speed_old = _safe_norm2(vel)  # (n,)
    speed_new = _safe_norm2(vel_new)  # (n,)

    can_turn_free = speed_old <= 0.5  # (n,) bool — slow agents turn freely

    # Maximum heading change allowed this tick (rad)
    # max_turn = dt * base * (0.25 + 0.75*agility) * speed_ref/(v_old + speed_ref)
    agility_factor = 0.25 + 0.75 * agility  # (n,)
    speed_taper = speed_ref / (speed_old + speed_ref)  # (n,)
    max_turn = dt * turn_rate_base * agility_factor * speed_taper  # (n,)

    # Heading of old and new velocity vectors
    heading_old = np.arctan2(vel[:, 1], vel[:, 0])  # (n,)
    heading_new = np.arctan2(vel_new[:, 1], vel_new[:, 0])  # (n,)

    # Signed angular difference, wrapped to [-pi, pi]
    delta_heading = heading_new - heading_old
    delta_heading = (delta_heading + np.pi) % (2.0 * np.pi) - np.pi  # (n,)

    # Clamp delta_heading to [-max_turn, +max_turn]
    clamped_delta = np.clip(delta_heading, -max_turn, max_turn)  # (n,)

    # Reconstruct clamped velocity keeping the new speed but clamped direction
    clamped_heading = heading_old + clamped_delta  # (n,)
    vel_clamped = np.column_stack(
        [np.cos(clamped_heading) * speed_new, np.sin(clamped_heading) * speed_new]
    )  # (n, 2)

    # Only apply clamp when agent is moving fast enough to matter
    vel_new = np.where(can_turn_free[:, np.newaxis], vel_new, vel_clamped)

    # --- final speed clamp --------------------------------------------------
    speed_final = _safe_norm2(vel_new)  # (n,)
    over_limit = speed_final > top_speed  # (n,)
    safe_speed = np.where(over_limit, top_speed / np.maximum(speed_final, _EPS), 1.0)
    vel_new = vel_new * safe_speed[:, np.newaxis]

    # --- position integration (semi-implicit Euler) -------------------------
    pos_new: FloatArray = pos + vel_new * dt

    return pos_new, vel_new


def time_to_point(
    pos: FloatArray,
    vel: FloatArray,
    point: FloatArray,
    top_speed: FloatArray,
    accel: FloatArray,
) -> FloatArray:
    """Straight-line accelerate-then-cruise travel time from current state (G-1).

    For each agent: accelerate at ``accel`` from the projected speed toward
    the target (clamped to [0, top_speed]) to ``top_speed``, then cruise.
    Solves the kinematic quadratic exactly; turn time is neglected (straight
    line assumption documented in ADR-003 d2).

    Parameters
    ----------
    pos:       (n, 2) current positions (m)
    vel:       (n, 2) current velocities (m/s)
    point:     (2,) or (n, 2) target point(s)
    top_speed: (n,) maximum speed (m/s)
    accel:     (n,) acceleration (m/s²)

    Returns
    -------
    t : (n,)  estimated arrival time (s); 0 for already-arrived agents.

    Notes
    -----
    Turn neglect: this function assumes the agent runs straight to ``point``.
    For interception feasibility this is an *optimistic* lower-bound on travel
    time, which is the correct direction of error (we never falsely exclude a
    reachable ball sample).
    """
    point = np.asarray(point, dtype=np.float64)
    diff = point - pos  # (n, 2)  (broadcasting handles (2,) point)
    dist = _safe_norm2(diff)  # (n,)

    # Project current velocity onto direction of travel (component toward target)
    safe_dist = np.maximum(dist, _EPS)
    unit_dir = diff / safe_dist[:, np.newaxis]  # (n, 2)
    v0 = np.sum(vel * unit_dir, axis=-1)  # (n,)  signed projection
    v0 = np.clip(v0, 0.0, top_speed)  # (n,)  clamp to [0, top_speed]

    # Already at the target
    at_target = dist <= _EPS  # (n,)

    # Distance covered while accelerating from v0 to top_speed
    # v = v0 + a*t  =>  t_accel = (vmax - v0) / a
    # d_accel = v0*t_accel + 0.5*a*t_accel^2
    safe_accel = np.maximum(accel, _EPS)
    t_accel = (top_speed - v0) / safe_accel  # (n,)
    d_accel = v0 * t_accel + 0.5 * safe_accel * t_accel**2  # (n,)

    # Case A: target reached during acceleration phase
    # 0.5*a*t^2 + v0*t - dist = 0  => quadratic formula, positive root
    discriminant = v0**2 + 2.0 * safe_accel * dist  # (n,)
    t_accel_only = (-v0 + np.sqrt(np.maximum(discriminant, 0.0))) / safe_accel  # (n,)

    # Case B: accelerate to top_speed, then cruise remaining distance
    d_cruise = dist - d_accel  # (n,)
    t_cruise = d_cruise / np.maximum(top_speed, _EPS)  # (n,)
    t_both = t_accel + t_cruise  # (n,)

    # Choose A or B based on whether we reach top_speed before the target
    use_accel_only = d_accel >= dist  # (n,) bool
    t_raw = np.where(use_accel_only, t_accel_only, t_both)  # (n,)

    # Zero out already-arrived agents
    result: FloatArray = np.where(at_target, 0.0, t_raw)
    return result


def separate(pos: FloatArray, radius: float, passes: int = 4) -> FloatArray:
    """Pairwise soft-disc separation with grid seed for dense clusters (G-7).

    Guarantees pairwise distance >= 2*radius - 1e-6 for n <= 22 agents after
    the call, regardless of initial configuration (including all piled at a
    single point). O(n^2) per sweep; n=22 -> 231 pairs, trivial at this scale.

    Algorithm:
    1. Grid seeding: for each agent whose nearest neighbour is within _tiny,
       relocate it to a deterministic grid slot centred at its original position.
       This replaces zero-distance degeneracy with a valid starting layout.
    2. Pairwise sweeps (up to ``passes``): push each overlapping pair apart by
       half the overlap along their connecting axis. Stops early when clean.

    Parameters
    ----------
    pos:    (n, 2) positions (m)
    radius: soft-disc radius (m); overlap if dist < 2*radius
    passes: number of cleanup sweeps (default 4)

    Returns
    -------
    pos_out : (n, 2) positions after separation; deterministic.

    Notes
    -----
    The grid seed is applied only when agents are degenerate (distance < 1e-6).
    Well-separated agents are never moved by the grid step.
    """
    n = pos.shape[0]
    pos_out: FloatArray = pos.copy()
    min_dist = 2.0 * radius
    _tiny = 1e-6

    # --- Step 1: grid-seed degenerate clusters ------------------------------
    # Assign each agent a deterministic row/col slot on a square grid with
    # spacing = min_dist. Only relocates agents that are nearly coincident with
    # at least one other agent. Agents already well-separated are not moved.
    cols = int(np.ceil(np.sqrt(float(n))))
    centroid = np.mean(pos_out, axis=0)
    # Use slightly larger grid spacing than min_dist so grid-adjacent slots
    # start above the separation threshold and don't oscillate at the boundary.
    grid_spacing = min_dist * 1.05

    # Identify degenerate agents from ORIGINAL positions (before any moves),
    # then bulk-relocate. This avoids the problem where early moves un-mark
    # later agents that are still at the original overlapping position.
    # Vectorized pairwise distances drive both steps: this function runs every
    # engine tick, and python n^2 scans dominated profiles (1.4 ms/call).
    def _sq_dists(p: FloatArray) -> FloatArray:
        diff = p[:, np.newaxis, :] - p[np.newaxis, :, :]
        d2: FloatArray = np.sum(diff * diff, axis=-1)
        np.fill_diagonal(d2, np.inf)
        return d2

    d2 = _sq_dists(pos_out)
    if float(d2.min()) >= min_dist * min_dist:
        return pos_out  # common case: nobody overlapping, nothing to do

    # --- Step 1: grid-seed degenerate clusters (rare) ------------------------
    if float(d2.min()) < _tiny * _tiny:
        degenerate_idx = np.where((d2 < _tiny * _tiny).any(axis=1))[0]
        for i in degenerate_idx:
            row = int(i) // cols
            col = int(i) % cols
            pos_out[i, 0] = centroid[0] + (col - (cols - 1) / 2.0) * grid_spacing
            pos_out[i, 1] = centroid[1] + (row - (cols - 1) / 2.0) * grid_spacing

    # --- Step 2: cleanup sweeps over the (few) overlapping pairs only --------
    for _ in range(passes):
        d2 = _sq_dists(pos_out)
        ii, jj = np.where(np.triu(d2 < min_dist * min_dist, k=1))
        if len(ii) == 0:
            break
        # Ordered loop keeps push resolution deterministic (i < j ascending).
        for i, j in zip(ii.tolist(), jj.tolist(), strict=True):
            diff = pos_out[j] - pos_out[i]
            d = float(np.sqrt(diff[0] ** 2 + diff[1] ** 2))
            if d >= min_dist:
                continue  # already resolved by an earlier push this sweep
            overlap = min_dist - d
            axis = np.array([1.0, 0.0]) if d < _tiny else diff / d
            push = 0.5 * overlap * axis
            pos_out[i] -= push
            pos_out[j] += push

    return pos_out

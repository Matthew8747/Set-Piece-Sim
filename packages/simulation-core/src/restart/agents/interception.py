"""Interception feasibility kernel.

Computes the earliest ball-flight sample each agent can feasibly intercept,
gated by reaction-time deadlines (G-3) and physical reach (G-1, G-2, G-4').

Design ref: ADR-003 d2 (precomputed flight oracle), d3 (reaction deadlines),
d4 (2.5-D kinematics — vertical interception via reach, not airborne state).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from restart.agents.kinematics import time_to_point
from restart.domain.vectors import FloatArray


def earliest_interception(
    pos: FloatArray,
    vel: FloatArray,
    top_speed: FloatArray,
    accel: FloatArray,
    reach: FloatArray,
    ready_time: FloatArray,
    ball_times: FloatArray,
    ball_pos: FloatArray,
) -> npt.NDArray[np.int64]:
    """Return the earliest interceptable ball-sample index for each agent (G-3).

    For each agent *i*, finds the smallest sample index *k* satisfying all of:

    1. ``ball_times[k] >= ready_time[i]``  — agent has reacted (G-3)
    2. ``ball_pos[k, 2] <= reach[i]``       — ball is within jump-reach height
       (G-4': vertical reach instead of airborne jump state)
    3. ``time_to_point(agent_i -> ball_pos[k, :2]) <= ball_times[k]``
       — agent can arrive before the ball does (straight-line optimistic
       lower bound; turn neglect documented in kinematics.time_to_point)

    Returns ``-1`` for any agent that cannot intercept any sample.

    Parameters
    ----------
    pos:        (n, 2)  agent positions (m, pitch plane)
    vel:        (n, 2)  agent velocities (m/s)
    top_speed:  (n,)    maximum speed (m/s)
    accel:      (n,)    acceleration (m/s²)
    reach:      (n,)    maximum contact height (m); maps to jump_reach_m (G-4')
    ready_time: (n,)    earliest time the agent can act (s); models reaction
                        latency (G-3): agent ignores information before this
    ball_times: (m,)    time of each ball-flight sample (s)
    ball_pos:   (m, 3)  position of each ball-flight sample (m; z=height)

    Returns
    -------
    result : (n,)  int64 array — sample index or -1

    Notes
    -----
    The feasibility matrix is (n x m) ~= 22 x 300 = 6,600 cells, evaluated
    with NumPy broadcasting — well within the per-tick budget (ADR-003 §2).
    """
    n = pos.shape[0]
    m = ball_times.shape[0]

    # --- build (n, m) feasibility matrix -----------------------------------

    # 1. Reaction gate: agent i can use sample k only if ball_times[k] >= ready_time[i]
    #    Shape: (n, m) via broadcasting (n,1) vs (m,)
    reacted = ready_time[:, np.newaxis] <= ball_times[np.newaxis, :]  # (n, m) bool

    # 2. Reach gate: ball height at sample k must be <= reach[i]
    #    Shape: (n, m)
    ball_z = ball_pos[:, 2]  # (m,)
    reachable = reach[:, np.newaxis] >= ball_z[np.newaxis, :]  # (n, m) bool

    # 3. Travel-time gate: for each (i, k) compute travel time from agent i to
    #    ball_pos[k, :2] and check it fits inside ball_times[k].
    #
    #    Vectorise over (n, m): broadcast pos/vel/top_speed/accel to (n*m, ...)
    #    then reshape result.
    ball_xy = ball_pos[:, :2]  # (m, 2)

    # Tile agent state to (n*m, 2) / (n*m,)
    pos_nm = np.repeat(pos, m, axis=0)  # (n*m, 2)
    vel_nm = np.repeat(vel, m, axis=0)  # (n*m, 2)
    top_nm = np.repeat(top_speed, m)  # (n*m,)
    accel_nm = np.repeat(accel, m)  # (n*m,)

    # Tile ball positions to (n*m, 2)
    target_nm = np.tile(ball_xy, (n, 1))  # (n*m, 2)

    travel = time_to_point(pos_nm, vel_nm, target_nm, top_nm, accel_nm)  # (n*m,)
    travel_nm = travel.reshape(n, m)  # (n, m)

    # Feasible when travel time <= ball arrival time (ball_times broadcast to (n,m))
    can_arrive = travel_nm <= ball_times[np.newaxis, :]  # (n, m)

    # Combined feasibility mask
    feasible = reacted & reachable & can_arrive  # (n, m)

    # --- find earliest feasible sample for each agent ----------------------
    result = np.full(n, -1, dtype=np.int64)
    for i in range(n):
        indices = np.where(feasible[i])[0]
        if indices.size > 0:
            result[i] = int(indices[0])  # smallest feasible index

    return result

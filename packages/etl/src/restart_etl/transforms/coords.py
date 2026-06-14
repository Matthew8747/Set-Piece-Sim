"""The one coordinate transform, owned in exactly one place (design doc 04 §4).

StatsBomb space: a 120x80 grid, origin **top-left**, the team in possession
always attacks toward x=120, y increases downward. Attacking goal mouth is the
segment x=120, y in [36, 44] (8 yd between posts on the 80-wide grid).

Canonical Restart frame: **105x68 m, origin at pitch center, attack left->right**
(attacking goal at +x). This matches the simulation engine, whose goal line sits
at x=+52.5 with posts at y=+/-3.66. Mapping:

    x_m = x_sb / 120 * 105 - 52.5        # [0,120]  -> [-52.5, +52.5]
    y_m = 34 - y_sb / 80 * 68            # [0,80] (down) -> [+34, -34] (up = +y)

The y flip makes +y "up the page" (left of the attacker), a standard math frame.
Sign is a convention; what matters is that it is applied here and nowhere else,
so freeze-frame defenders and the shot location share one frame. Property tests
pin the corners, the goal mouth, and the in-bounds invariant.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

# StatsBomb grid extent (their pitch model is always 120x80, regardless of the
# real stadium dimensions).
SB_LENGTH = 120.0
SB_WIDTH = 80.0

# Canonical metric pitch (FIFA standard, design doc + engine constants).
PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
HALF_LENGTH_M = PITCH_LENGTH_M / 2.0  # 52.5
HALF_WIDTH_M = PITCH_WIDTH_M / 2.0  # 34.0

# Attacking goal in the canonical frame (matches restart.engine).
GOAL_X_M = HALF_LENGTH_M  # 52.5
GOAL_HALF_WIDTH_M = 3.66  # 7.32 m mouth / 2

FloatArr = npt.NDArray[np.float64]


def x_to_m(x_sb: float) -> float:
    """StatsBomb length coordinate -> metres, center origin, attack +x."""
    return x_sb / SB_LENGTH * PITCH_LENGTH_M - HALF_LENGTH_M


def y_to_m(y_sb: float) -> float:
    """StatsBomb width coordinate (down-positive) -> metres, up-positive, center origin."""
    return HALF_WIDTH_M - y_sb / SB_WIDTH * PITCH_WIDTH_M


def to_pitch_xy(x_sb: float, y_sb: float) -> tuple[float, float]:
    """Transform a single StatsBomb (x, y) to the canonical metric frame."""
    return x_to_m(x_sb), y_to_m(y_sb)


def to_pitch_xy_array(xy_sb: FloatArr) -> FloatArr:
    """Vectorised transform of an ``(n, 2)`` StatsBomb coordinate array."""
    if xy_sb.ndim != 2 or xy_sb.shape[1] != 2:
        raise ValueError(f"expected (n, 2) array, got {xy_sb.shape}")
    out = np.empty_like(xy_sb, dtype=np.float64)
    out[:, 0] = xy_sb[:, 0] / SB_LENGTH * PITCH_LENGTH_M - HALF_LENGTH_M
    out[:, 1] = HALF_WIDTH_M - xy_sb[:, 1] / SB_WIDTH * PITCH_WIDTH_M
    return out


def shot_distance_m(x_m: float, y_m: float) -> float:
    """Euclidean distance from a pitch point to the centre of the attacking goal."""
    return float(np.hypot(GOAL_X_M - x_m, 0.0 - y_m))


def shot_angle_rad(x_m: float, y_m: float) -> float:
    """Opening angle (radians) of the goal mouth seen from a pitch point.

    Posts at (GOAL_X_M, +/-GOAL_HALF_WIDTH_M). Zero when the point is on the goal
    line outside the posts; widest from straight in front near the line. This is
    the standard xG angle feature and mirrors the engine's ``_goal_opening_angle``.
    """
    a = np.array([GOAL_X_M - x_m, -GOAL_HALF_WIDTH_M - y_m])
    b = np.array([GOAL_X_M - x_m, GOAL_HALF_WIDTH_M - y_m])
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom < 1e-9:
        return 0.0
    cosang = float(np.dot(a, b) / denom)
    return float(np.arccos(max(-1.0, min(1.0, cosang))))


def in_bounds_m(x_m: float, y_m: float, tol: float = 1e-6) -> bool:
    """True if a metric point lies on the pitch (within ``tol``)."""
    return abs(x_m) <= HALF_LENGTH_M + tol and abs(y_m) <= HALF_WIDTH_M + tol

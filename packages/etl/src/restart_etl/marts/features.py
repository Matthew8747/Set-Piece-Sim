"""Freeze-frame traffic features for set-piece shots (the xG feature surface).

Every feature is computed in the canonical metric frame from the transformed
freeze frame: geometry to the goal plus how crowded the shooting lane is. These
mirror the ``ShotContext`` the simulator emits (restart.engine.xg) so that real
training features and simulated scoring features are the same quantities.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from restart_etl.transforms.coords import (
    GOAL_HALF_WIDTH_M,
    GOAL_X_M,
    shot_angle_rad,
    shot_distance_m,
)

# Penalty-area bounds in the canonical frame (16.5 m box, 40.32 m wide).
_BOX_X_MIN = GOAL_X_M - 16.5
_BOX_HALF_Y = 20.16
_POST_L = (GOAL_X_M, -GOAL_HALF_WIDTH_M)
_POST_R = (GOAL_X_M, GOAL_HALF_WIDTH_M)


@dataclass(frozen=True, slots=True)
class ShotFeatures:
    distance_m: float
    angle_rad: float
    defenders_in_cone: int
    nearest_def_dist_m: float
    defenders_within_3m: int
    n_defenders: int
    n_teammates: int
    n_def_in_box: int
    gk_dist_to_goal_m: float
    gk_dist_to_shot_m: float
    gk_lateral_m: float
    has_gk: bool

    def as_dict(self) -> dict[str, float | int | bool]:
        return asdict(self)


def _sign(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (ax - cx) * (by - cy) - (bx - cx) * (ay - cy)


def _in_triangle(
    px: float, py: float, a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]
) -> bool:
    d1 = _sign(px, py, a[0], a[1], b[0], b[1])
    d2 = _sign(px, py, b[0], b[1], c[0], c[1])
    d3 = _sign(px, py, c[0], c[1], a[0], a[1])
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


def compute_features(
    x_m: float, y_m: float, freeze_frame: list[dict[str, float | bool]]
) -> ShotFeatures:
    """Compute traffic + geometry features for a shot at ``(x_m, y_m)``.

    ``freeze_frame`` items are dicts with keys ``x_m``, ``y_m``, ``teammate``,
    ``is_gk`` (as produced by staging). When the frame is empty, traffic counts
    are zero and GK distances default to the goal line - callers gate on
    ``has_gk`` / a separate has_freeze_frame flag and impute downstream.
    """
    distance = shot_distance_m(x_m, y_m)
    angle = shot_angle_rad(x_m, y_m)

    opponents = [p for p in freeze_frame if not bool(p["teammate"])]
    teammates = [p for p in freeze_frame if bool(p["teammate"])]
    outfield_opp = [p for p in opponents if not bool(p["is_gk"])]

    cone_apex = (x_m, y_m)
    in_cone = 0
    near = float("inf")
    within3 = 0
    in_box = 0
    for p in outfield_opp:
        ox, oy = float(p["x_m"]), float(p["y_m"])
        if _in_triangle(ox, oy, cone_apex, _POST_L, _POST_R):
            in_cone += 1
        d = ((ox - x_m) ** 2 + (oy - y_m) ** 2) ** 0.5
        near = min(near, d)
        if d < 3.0:
            within3 += 1
        if ox >= _BOX_X_MIN and abs(oy) <= _BOX_HALF_Y:
            in_box += 1

    gk = next((p for p in opponents if bool(p["is_gk"])), None)
    if gk is not None:
        gx, gy = float(gk["x_m"]), float(gk["y_m"])
        gk_goal = ((GOAL_X_M - gx) ** 2 + (0.0 - gy) ** 2) ** 0.5
        gk_shot = ((gx - x_m) ** 2 + (gy - y_m) ** 2) ** 0.5
        gk_lat = abs(gy)
        has_gk = True
    else:
        gk_goal = 0.0
        gk_shot = distance
        gk_lat = 0.0
        has_gk = False

    return ShotFeatures(
        distance_m=distance,
        angle_rad=angle,
        defenders_in_cone=in_cone,
        nearest_def_dist_m=(0.0 if near == float("inf") else near),
        defenders_within_3m=within3,
        n_defenders=len(opponents),
        n_teammates=len(teammates),
        n_def_in_box=in_box,
        gk_dist_to_goal_m=gk_goal,
        gk_dist_to_shot_m=gk_shot,
        gk_lateral_m=gk_lat,
        has_gk=has_gk,
    )

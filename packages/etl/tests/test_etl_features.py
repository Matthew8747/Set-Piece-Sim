"""Traffic-feature extraction from freeze frames."""

from __future__ import annotations

from restart_etl.marts.features import compute_features
from restart_etl.transforms.coords import GOAL_X_M


def _ff(x: float, y: float, teammate: bool, is_gk: bool) -> dict[str, float | bool]:
    return {"x_m": x, "y_m": y, "teammate": teammate, "is_gk": is_gk}


def test_defender_in_cone_and_nearest() -> None:
    # Shooter 8 m out, central. One defender directly in the lane, one wide.
    shot_x, shot_y = GOAL_X_M - 8.0, 0.0
    frame = [
        _ff(GOAL_X_M - 4.0, 0.0, teammate=False, is_gk=False),  # in cone, 4 m away
        _ff(GOAL_X_M - 4.0, 25.0, teammate=False, is_gk=False),  # wide, not in cone
        _ff(GOAL_X_M, 0.0, teammate=False, is_gk=True),  # GK on the line
        _ff(shot_x, shot_y, teammate=True, is_gk=False),  # the shooter's team
    ]
    f = compute_features(shot_x, shot_y, frame)
    assert f.defenders_in_cone == 1
    assert f.n_defenders == 3
    assert f.n_teammates == 1
    assert f.has_gk
    assert abs(f.nearest_def_dist_m - 4.0) < 1e-6
    assert f.gk_lateral_m == 0.0


def test_empty_frame_defaults() -> None:
    f = compute_features(GOAL_X_M - 10.0, 0.0, [])
    assert f.defenders_in_cone == 0
    assert f.n_defenders == 0
    assert not f.has_gk
    assert f.nearest_def_dist_m == 0.0

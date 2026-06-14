"""Property + landmark tests for the one coordinate transform."""

from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st

from restart_etl.transforms.coords import (
    GOAL_HALF_WIDTH_M,
    GOAL_X_M,
    HALF_LENGTH_M,
    HALF_WIDTH_M,
    in_bounds_m,
    shot_angle_rad,
    shot_distance_m,
    to_pitch_xy,
)


def test_corners_map_to_pitch_corners() -> None:
    # StatsBomb (0,0) is the top-left; (120,80) bottom-right.
    assert to_pitch_xy(0.0, 0.0) == (-HALF_LENGTH_M, HALF_WIDTH_M)
    assert to_pitch_xy(120.0, 80.0) == (HALF_LENGTH_M, -HALF_WIDTH_M)


def test_center_maps_to_origin() -> None:
    x, y = to_pitch_xy(60.0, 40.0)
    assert abs(x) < 1e-9
    assert abs(y) < 1e-9


def test_attacking_goal_at_positive_x() -> None:
    # StatsBomb goal mouth is x=120, y in [36,44]; maps to x=+52.5 near y=0.
    x, y = to_pitch_xy(120.0, 40.0)
    assert math.isclose(x, GOAL_X_M)
    assert abs(y) < 1e-9


@given(
    x=st.floats(min_value=0.0, max_value=120.0),
    y=st.floats(min_value=0.0, max_value=80.0),
)
def test_in_bounds_invariant(x: float, y: float) -> None:
    xm, ym = to_pitch_xy(x, y)
    assert in_bounds_m(xm, ym)


def test_distance_and_angle_on_goal_line() -> None:
    # Straight in front, 11 m out: distance ~ 11, angle positive and < pi.
    d = shot_distance_m(GOAL_X_M - 11.0, 0.0)
    assert math.isclose(d, 11.0, abs_tol=1e-6)
    a = shot_angle_rad(GOAL_X_M - 11.0, 0.0)
    assert 0.0 < a < math.pi


def test_angle_zero_on_goal_line_outside_posts() -> None:
    # On the goal line, well wide of the post: the mouth subtends ~0 angle.
    a = shot_angle_rad(GOAL_X_M, GOAL_HALF_WIDTH_M + 10.0)
    assert a < 1e-6

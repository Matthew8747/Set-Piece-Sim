"""Canonical pitch geometry and coordinate frame.

Coordinate frame (the project-wide contract):

* Units: meters (SI everywhere in the simulation core).
* Pitch: 105 m x 68 m (FIFA-preferred international dimensions).
* Origin: pitch center. x along the long axis, y along the short axis,
  z vertical (up). The attacking team always attacks toward +x.
* Therefore x is in [-52.5, 52.5] and y is in [-34.0, 34.0] on the pitch.

All external data sources (StatsBomb's 120x80 yard-ish frame, FBref, etc.) are
converted into this frame at the ETL staging boundary and never leak through.
"""

from typing import Final

PITCH_LENGTH_M: Final[float] = 105.0
PITCH_WIDTH_M: Final[float] = 68.0

GOAL_WIDTH_M: Final[float] = 7.32
GOAL_HEIGHT_M: Final[float] = 2.44

HALF_LENGTH_M: Final[float] = PITCH_LENGTH_M / 2
HALF_WIDTH_M: Final[float] = PITCH_WIDTH_M / 2


#: Goal mouth half-width (posts at y = +/- 3.66 m on the goal line).
GOAL_HALF_WIDTH_M: Final[float] = GOAL_WIDTH_M / 2

#: Crossbar underside height.
CROSSBAR_HEIGHT_M: Final[float] = GOAL_HEIGHT_M


def is_in_goal_mouth(y: float, z: float) -> bool:
    """Return ``True`` if a point on a goal-line plane (x = +/-52.5) lies
    inside the goal mouth: between the posts and under the bar.

    Ball-center based (the ~"whole ball over the line" subtlety of Law 10 is
    below this model's fidelity - assumption P-15 in the assumptions registry).
    """
    return abs(y) <= GOAL_HALF_WIDTH_M and 0.0 <= z <= CROSSBAR_HEIGHT_M


def corner_position(left_side: bool, attacking_positive_x: bool = True) -> tuple[float, float]:
    """Corner-flag coordinates (x, y) for the attacking team's corner kick.

    ``left_side`` is from the attacking team's perspective facing the goal
    they attack (+x by project convention).
    """
    x = HALF_LENGTH_M if attacking_positive_x else -HALF_LENGTH_M
    y = HALF_WIDTH_M if left_side else -HALF_WIDTH_M
    return (x, y)


def is_on_pitch(x: float, y: float) -> bool:
    """Return ``True`` if the point (x, y) lies on the playing surface.

    Boundary lines are part of the pitch (the ball on the line is in play),
    so bounds are inclusive. Non-finite inputs (NaN, +/-inf) are off-pitch:
    NaN comparisons are False, which falls through to ``False`` naturally,
    but we rely on the comparison semantics rather than an explicit check -
    documented here so the behavior is intentional, not accidental.
    """
    return -HALF_LENGTH_M <= x <= HALF_LENGTH_M and -HALF_WIDTH_M <= y <= HALF_WIDTH_M

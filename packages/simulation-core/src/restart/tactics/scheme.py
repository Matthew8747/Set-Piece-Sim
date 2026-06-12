"""DefensiveScheme — validated defensive configuration for set pieces.

The scheme is orthogonal to the attacking routine (ADR-004 d1): the optimizer
searches the attacking space against a *fixed* opponent scheme, so defence must
be a separate first-class document.

Defenders defend the goal at +x (they face the attacking team). Zonal points
therefore cluster in/around the box, x ∈ [40, 52.5].

The scheme always describes a *complete* defensive setup: 10 outfield players
are fully accounted for across zonal positions, man-markers, and FK wall.
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from restart.tactics.routine import PitchPoint


class DefensiveScheme(BaseModel):
    """A complete defensive scheme for a set-piece delivery.

    Invariant: len(zonal_points) + n_man_markers + wall_size == 10
    (all 10 outfield defenders are assigned).

    Attributes
    ----------
    name:
        Human-readable label (e.g. "zonal_6_2", "man_heavy").
    zonal_points:
        Pitch positions where zonal defenders start; 0-10 points, all in
        the defending half. Defenders protect space near these coordinates.
    n_man_markers:
        Number of man-marking defenders. They are assigned greedily by
        compile_scenario to the highest-threat attackers.
    gk_position:
        Goalkeeper starting position. Defaults to just off the goal-line
        center (51.5, 0) — realistic set-piece positioning.
    wall_size:
        Number of defenders in the FK wall (0 for corners, 0-6 for FKs).
        The wall is positioned by compile_scenario at 9.15 m from kick_pos.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    zonal_points: tuple[PitchPoint, ...] = Field(default=(), max_length=10)
    # le=10 permits pure man-marking setups (all ten outfielders marking).
    n_man_markers: int = Field(default=0, ge=0, le=10)
    gk_position: PitchPoint = Field(default_factory=lambda: PitchPoint(x=51.5, y=0.0))
    wall_size: int = Field(default=0, ge=0, le=6)

    @model_validator(mode="after")
    def _complete_defensive_setup(self) -> Self:
        total = len(self.zonal_points) + self.n_man_markers + self.wall_size
        if total != 10:
            msg = (
                f"DefensiveScheme '{self.name}': "
                f"len(zonal_points)={len(self.zonal_points)} + "
                f"n_man_markers={self.n_man_markers} + "
                f"wall_size={self.wall_size} = {total} != 10 "
                f"(all 10 outfield defenders must be assigned)"
            )
            raise ValueError(msg)
        return self

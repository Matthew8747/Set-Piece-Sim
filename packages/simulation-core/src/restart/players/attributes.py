"""Player attribute model and the kernel-facing column contract.

Attributes are the capability envelope consumed by the agent layer (design doc
05 §3.1; DB schema doc 03 `player_attributes`). Two representations:

* ``PlayerAttributes`` — frozen pydantic model, validated bounds, the boundary
  type (built by hand, by ETL in Phase 4, or by the UI later).
* The attribute **matrix** — ``(n_players, N_ATTR)`` float64, column order
  fixed by :class:`Attr`. This is what SimPrograms carry and what (future)
  Numba kernels index. **Column order is a compiled-program ABI: append-only.**

Bounds are physical plausibility rails, not league statistics; defaults are a
mid-level professional. Sources for ranges: sprint literature (top speed
8.5-9.8 m/s elite; accel 2-8 m/s^2 sustained), reaction-time literature
(0.15-0.45 s for choice reactions), highest recorded header contacts ~= 2.9 m
(jump_reach = standing reach + jump). Tagged G-1 in the assumptions registry.
"""

from enum import IntEnum
from typing import Final

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from restart.domain.vectors import FloatArray


class Attr(IntEnum):
    """Column indices of the attribute matrix. Append-only (compiled-program ABI)."""

    TOP_SPEED = 0  # m/s
    ACCEL = 1  # m/s^2
    REACTION_TIME = 2  # s
    AGILITY = 3  # 0-1 (scales turn-rate limit)
    JUMP_REACH = 4  # m (max contact height: standing reach + jump)
    HEADING = 5  # 0-1 (aerial contest + header accuracy)
    STRENGTH = 6  # 0-1 (duel weight)
    MARKING = 7  # 0-1 (defensive tracking fidelity)
    AWARENESS_OFF = 8  # 0-1 (run-timing precision)
    AWARENESS_DEF = 9  # 0-1 (ball-tracking / second-ball anticipation)
    DELIVERY = 10  # 0-1 (set-piece delivery execution; kickers)
    HEIGHT = 11  # m (body height; provenance for jump_reach, UI display)


ATTR_COLUMNS: Final[tuple[str, ...]] = tuple(a.name.lower() for a in Attr)
N_ATTR: Final[int] = len(Attr)


class PlayerAttributes(BaseModel):
    """Validated capability envelope. Frozen; defaults = mid-level professional."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    top_speed_ms: float = Field(default=7.8, ge=5.5, le=9.8)
    accel_ms2: float = Field(default=5.0, ge=2.0, le=8.0)
    reaction_time_s: float = Field(default=0.25, ge=0.15, le=0.45)
    agility: float = Field(default=0.5, ge=0.0, le=1.0)
    jump_reach_m: float = Field(default=2.55, ge=2.10, le=3.00)
    heading: float = Field(default=0.5, ge=0.0, le=1.0)
    strength: float = Field(default=0.5, ge=0.0, le=1.0)
    marking: float = Field(default=0.5, ge=0.0, le=1.0)
    awareness_off: float = Field(default=0.5, ge=0.0, le=1.0)
    awareness_def: float = Field(default=0.5, ge=0.0, le=1.0)
    delivery: float = Field(default=0.5, ge=0.0, le=1.0)
    height_m: float = Field(default=1.83, ge=1.60, le=2.10)

    def to_row(self) -> FloatArray:
        """Pack into a matrix row, column order per :class:`Attr`."""
        row = np.empty(N_ATTR, dtype=np.float64)
        row[Attr.TOP_SPEED] = self.top_speed_ms
        row[Attr.ACCEL] = self.accel_ms2
        row[Attr.REACTION_TIME] = self.reaction_time_s
        row[Attr.AGILITY] = self.agility
        row[Attr.JUMP_REACH] = self.jump_reach_m
        row[Attr.HEADING] = self.heading
        row[Attr.STRENGTH] = self.strength
        row[Attr.MARKING] = self.marking
        row[Attr.AWARENESS_OFF] = self.awareness_off
        row[Attr.AWARENESS_DEF] = self.awareness_def
        row[Attr.DELIVERY] = self.delivery
        row[Attr.HEIGHT] = self.height_m
        return row

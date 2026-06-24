"""Routine Spec rs/1.0 - validated pydantic document for set-piece attacking routines.

Implements ADR-004 decision 1-3:
* Delivery + per-role assignments (start, run legs with triggers/delays, intent).
* Validation rejects, never repairs (ADR-004 d2).
* Triggers are a small closed vocabulary compiled to absolute times (ADR-004 d3).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from restart.domain.pitch import is_on_pitch
from restart.domain.vectors import FloatArray

# ---------------------------------------------------------------------------
# Closed vocabularies (compiled to int codes by compile.py)
# ---------------------------------------------------------------------------


class SetPiece(StrEnum):
    """The type of dead-ball restart."""

    CORNER = "corner"
    FREE_KICK = "free_kick"


class DeliveryType(StrEnum):
    """How the ball is struck."""

    INSWINGER = "inswinger"
    OUTSWINGER = "outswinger"
    DRIVEN = "driven"
    FLOATED = "floated"
    SHORT = "short"


class Intent(StrEnum):
    """The tactical role of a runner's assignment.

    Code mapping exported as INTENT_CODES; order matches SimProgram int8 encoding.
    """

    ATTACK_BALL = "attack_ball"  # 0 - primary aerial/first-contact threat
    DECOY = "decoy"  # 1 - draws markers away
    SCREEN = "screen"  # 2 - occupies GK / blocks passing lanes
    SECOND_BALL = "second_ball"  # 3 - edge-of-box rebound collector
    SHORT_OPTION = "short_option"  # 4 - short-delivery lay-off target


class Trigger(StrEnum):
    """When a run leg starts relative to the delivery.

    Code mapping exported as TRIGGER_CODES; order matches SimProgram int8 encoding.
    KICK_APPROACH ~= t - 0.5 s, KICK = t0, BALL_APEX = peak of flight arc.
    """

    KICK_APPROACH = "kick_approach"  # 0
    KICK = "kick"  # 1
    BALL_APEX = "ball_apex"  # 2


#: Intent → int8 code used in SimProgram att_intent arrays. Append-only (ABI).
INTENT_CODES: dict[Intent, int] = {
    Intent.ATTACK_BALL: 0,
    Intent.DECOY: 1,
    Intent.SCREEN: 2,
    Intent.SECOND_BALL: 3,
    Intent.SHORT_OPTION: 4,
}

#: Trigger → int8 code used in SimProgram att_legs_trigger arrays. Append-only.
TRIGGER_CODES: dict[Trigger, int] = {
    Trigger.KICK_APPROACH: 0,
    Trigger.KICK: 1,
    Trigger.BALL_APEX: 2,
}


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


class PitchPoint(BaseModel):
    """A 2-D point on the pitch, validated against the coordinate frame.

    Coordinate frame: origin center, x in [-52.5, 52.5], y in [-34, 34].
    The attacking team attacks toward +x; their target goal is at (52.5, 0).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    x: float
    y: float

    @model_validator(mode="after")
    def _must_be_on_pitch(self) -> Self:
        if not is_on_pitch(self.x, self.y):
            msg = (
                f"PitchPoint({self.x}, {self.y}) is off-pitch; "
                f"valid range x∈[-52.5, 52.5], y∈[-34.0, 34.0]"
            )
            raise ValueError(msg)
        return self

    def as_array(self) -> FloatArray:
        """Return shape-(2,) float64 array [x, y]."""
        return np.array([self.x, self.y], dtype=np.float64)


class RunLeg(BaseModel):
    """One segment of a player's scripted run.

    Players follow a sequence of up to 3 RunLegs; each leg begins when its
    trigger fires (plus optional delay), and the player moves to `to`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    to: PitchPoint
    trigger: Trigger = Trigger.KICK
    delay_s: float = Field(default=0.0, ge=0.0, le=2.0)


class Assignment(BaseModel):
    """A player's tactical assignment within the routine.

    `role` is a human-readable string identity (e.g. "near_post_runner");
    it is used as a dict key in Scenario.role_assignments to map role → player_id.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: str = Field(min_length=1, max_length=32)
    start: PitchPoint
    runs: tuple[RunLeg, ...] = Field(default=(), max_length=3)
    intent: Intent

    @field_validator("role")
    @classmethod
    def _no_whitespace(cls, v: str) -> str:
        if any(c.isspace() for c in v):
            msg = f"role {v!r} must not contain whitespace"
            raise ValueError(msg)
        return v


class Delivery(BaseModel):
    """The delivery specification for the set piece.

    speed_ms: ball launch speed in m/s.
    spin_rps: spin magnitude in revolutions per second; direction is encoded
    by compile_scenario based on delivery type and corner side.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: DeliveryType
    target: PitchPoint
    speed_ms: float = Field(default=24.0, ge=10.0, le=35.0)
    spin_rps: float = Field(default=8.0, ge=0.0, le=12.0)


# ---------------------------------------------------------------------------
# Root document
# ---------------------------------------------------------------------------


class RoutineSpec(BaseModel):
    """The validated rs/1.0 routine specification document.

    Serializes losslessly (pydantic) into `routines.spec` JSONB (DB schema doc 03).
    Schema evolution mints rs/2.0 and a migration shim (ADR-004 d5).

    Validation rules (ADR-004 d2 - rejects, never repairs):
    * roles must be unique across assignments.
    * For CORNER with non-SHORT delivery: at least one ATTACK_BALL intent required.
    * For CORNER routines, the delivery target must be in the attacking quarter
      (x > 26.25 - the midpoint between halfway line and goal line).
    * FREE_KICK routines have no aerial-intent requirement (a direct shot has
      no runners; the rebounder role uses SECOND_BALL which is valid).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    spec_version: Literal["rs/1.0"] = "rs/1.0"
    set_piece: SetPiece
    name: str = Field(min_length=1, max_length=80)
    delivery: Delivery
    assignments: tuple[Assignment, ...] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def _validate_routine(self) -> Self:
        # Roles must be unique
        roles = [a.role for a in self.assignments]
        if len(set(roles)) != len(roles):
            seen: set[str] = set()
            dupes = [r for r in roles if r in seen or seen.add(r)]  # type: ignore[func-returns-value]
            msg = f"duplicate roles in assignments: {dupes}"
            raise ValueError(msg)

        # Corner-only: at least one ATTACK_BALL unless SHORT delivery.
        # FREE_KICK routines are exempt: a direct free kick shot has no aerial
        # runner assignments; rebounder uses SECOND_BALL, which is correct.
        if self.set_piece == SetPiece.CORNER and self.delivery.type != DeliveryType.SHORT:
            has_attack_ball = any(a.intent == Intent.ATTACK_BALL for a in self.assignments)
            if not has_attack_ball:
                msg = (
                    "at least one assignment must have intent=ATTACK_BALL "
                    f"(CORNER delivery type is {self.delivery.type!r}, not SHORT)"
                )
                raise ValueError(msg)

        # Corner: delivery target must be in attacking quarter (x > 26.25)
        if self.set_piece == SetPiece.CORNER and self.delivery.target.x <= 26.25:
            msg = (
                f"CORNER delivery target x={self.delivery.target.x} is not in the "
                f"attacking quarter (x > 26.25); corners must target the opponent's half"
            )
            raise ValueError(msg)

        return self

"""Typed simulation events.

Frozen, slotted dataclasses: cheap to create in loops, hashable-by-identity,
and serializable by the storage layer later (each event knows its ``kind``).
Event times/positions are refined by in-step linear interpolation (P-14), so
they are more precise than the integrator grid.

The Phase-1 vocabulary covers ball flight. Match events (first contact, shot,
clearance, ...) extend this module in Phases 2-3 — same base, richer kinds.
"""

from dataclasses import dataclass
from enum import StrEnum

from restart.domain.vectors import FloatArray


class TerminationReason(StrEnum):
    GOAL = "goal"
    OUT_OF_PLAY = "out_of_play"
    REST = "rest"
    MAX_TIME = "max_time"


@dataclass(frozen=True, slots=True)
class SimEvent:
    """Base event: something noteworthy at a time and place."""

    time_s: float
    position: FloatArray  # (3,) meters, canonical frame

    @property
    def kind(self) -> str:
        return type(self).__name__.removesuffix("Event").lower()


@dataclass(frozen=True, slots=True)
class LaunchEvent(SimEvent):
    """Ball set in motion (kick, throw, header onset)."""

    speed_ms: float
    spin_rps: float


@dataclass(frozen=True, slots=True)
class ApexEvent(SimEvent):
    """Highest point of an airborne arc."""


@dataclass(frozen=True, slots=True)
class BounceEvent(SimEvent):
    """Ground contact that returned the ball to flight."""

    impact_speed_ms: float
    #: Kinetic energy retained across the bounce, in (0, 1].
    energy_retained: float


@dataclass(frozen=True, slots=True)
class GoalEvent(SimEvent):
    """Ball center crossed a goal-line plane inside the goal mouth (P-15)."""

    entry_y_m: float
    entry_z_m: float


@dataclass(frozen=True, slots=True)
class OutOfPlayEvent(SimEvent):
    """Ball center crossed a touchline or goal-line outside the mouth."""

    boundary: str  # 'touchline+y' | 'touchline-y' | 'goal_line+x' | 'goal_line-x'


@dataclass(frozen=True, slots=True)
class RestEvent(SimEvent):
    """Ball decelerated to rest on the pitch."""

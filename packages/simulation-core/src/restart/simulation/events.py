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


# --- Match events (Phase 2: set-piece engine vocabulary) ---------------------


class SetPieceOutcome(StrEnum):
    """Terminal classification of one simulated set piece (ADR-003 d10)."""

    GOAL = "goal"
    SAVED = "saved"
    OFF_TARGET = "off_target"
    CLEARED = "cleared"
    KEEPER_CLAIM = "keeper_claim"
    SECOND_BALL_ATTACK = "second_ball_attack"
    SECOND_BALL_DEFENSE = "second_ball_defense"
    OUT_OF_PLAY = "out_of_play"


@dataclass(frozen=True, slots=True)
class FirstContactEvent(SimEvent):
    """First deliberate touch on the delivered ball."""

    player_id: str
    team: str  # 'attack' | 'defense'
    contact_height_m: float


@dataclass(frozen=True, slots=True)
class ShotEvent(SimEvent):
    """Shot attempt; fields double as xG features (design review §1).

    ``xg`` is the real-data model's scored P(goal) for this strike when a scorer
    is wired into the engine (Phase 4), else ``None``. The Monte Carlo report
    averages it into ``mean_xg``.
    """

    player_id: str
    distance_m: float
    angle_rad: float  # goal-mouth opening angle from shot location
    is_header: bool
    speed_ms: float
    defenders_within_3m: int
    xg: float | None = None


@dataclass(frozen=True, slots=True)
class ClearanceEvent(SimEvent):
    player_id: str


@dataclass(frozen=True, slots=True)
class KeeperClaimEvent(SimEvent):
    player_id: str


@dataclass(frozen=True, slots=True)
class SaveEvent(SimEvent):
    player_id: str  # the goalkeeper
    shot_speed_ms: float


@dataclass(frozen=True, slots=True)
class SecondBallEvent(SimEvent):
    """Untouched delivery resolved at landing: nearest-player recovery."""

    player_id: str
    team: str  # 'attack' | 'defense'

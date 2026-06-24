"""Typed staging rows (pydantic = the schema contract at the staging boundary).

A staging row stays close to the source - one row per set-piece shot - but with
units standardized: coordinates in the canonical 105x68 m frame, the freeze
frame transformed into the same frame and carried as JSON for the marts to turn
into scalar traffic features. Validation here is the schema gate (doc 04 §5):
types and nullability are pinned, so a malformed source event fails loudly.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Set-piece origin taxonomy. We ingest corners and free kicks (the simulator's
# domain); throw-ins and open play are excluded from the xG training corpus to
# keep simulated shot contexts on-manifold (doc 06 §2.3).
SET_PIECE_TYPES = ("corner", "free_kick")

# Phase taxonomy (doc 06 §2.1): direct = the taker shoots; first_contact = a
# first-time contact off the delivery (header/volley); second_ball = a controlled
# or rebounded strike from the second phase.
SET_PIECE_PHASES = ("direct", "first_contact", "second_ball")

BODY_PART_GROUPS = ("foot", "head", "other")


class FreezeFramePlayer(BaseModel):
    """One player in a shot freeze frame, in canonical metric coordinates."""

    model_config = {"frozen": True}

    x_m: float
    y_m: float
    teammate: bool  # True = shooter's team; False = opponent (defender/GK)
    is_gk: bool


class StagingShot(BaseModel):
    """One set-piece shot, typed and coordinate-standardized."""

    model_config = {"frozen": True}

    shot_id: str
    match_id: int
    competition: str
    period: int
    minute: int
    second: int
    team_id: int
    team: str
    player_id: int
    player: str
    position: str
    play_pattern: str
    set_piece_type: str  # in SET_PIECE_TYPES
    set_piece_phase: str  # in SET_PIECE_PHASES
    shot_type: str  # StatsBomb shot.type (Open Play / Free Kick / Corner)
    body_part: str  # raw StatsBomb body part
    body_part_group: str  # in BODY_PART_GROUPS
    technique: str
    outcome: str
    is_goal: int  # 0/1 label
    x_m: float
    y_m: float
    end_x_m: float | None
    end_y_m: float | None
    statsbomb_xg: float | None  # reference only - never a feature or the label
    under_pressure: bool
    freeze_frame: list[FreezeFramePlayer] = Field(default_factory=list)
    has_freeze_frame: bool
    source: str = "statsbomb_open_data"

"""Player and position-group entities (boundary types; never in hot loops)."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from restart.players.attributes import PlayerAttributes


class PositionGroup(StrEnum):
    GK = "GK"
    DF = "DF"
    MF = "MF"
    FW = "FW"


class Player(BaseModel):
    """A footballer. Identity + capability envelope; tactical role is assigned
    per scenario (Routine Spec), not stored on the player."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    player_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=80)
    position_group: PositionGroup
    attributes: PlayerAttributes = Field(default_factory=PlayerAttributes)

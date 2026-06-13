"""Team entity: a squad of players with unique identities."""

from typing import Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from restart.domain.vectors import FloatArray
from restart.players.attributes import N_ATTR
from restart.players.player import Player, PositionGroup


class Team(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    team_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=80)
    players: tuple[Player, ...] = Field(min_length=11)

    @model_validator(mode="after")
    def _unique_ids_and_a_keeper(self) -> Self:
        ids = [p.player_id for p in self.players]
        if len(set(ids)) != len(ids):
            msg = f"duplicate player_id in team {self.team_id!r}"
            raise ValueError(msg)
        if not any(p.position_group is PositionGroup.GK for p in self.players):
            msg = f"team {self.team_id!r} has no goalkeeper"
            raise ValueError(msg)
        return self

    def attribute_matrix(self, player_ids: list[str]) -> FloatArray:
        """Stack the named players into an ``(n, N_ATTR)`` matrix (SimProgram input).

        Order follows ``player_ids`` (the lineup order), not squad order.
        """
        by_id = {p.player_id: p for p in self.players}
        missing = [pid for pid in player_ids if pid not in by_id]
        if missing:
            msg = f"player_ids not in team {self.team_id!r}: {missing}"
            raise ValueError(msg)
        out = np.empty((len(player_ids), N_ATTR), dtype=np.float64)
        for i, pid in enumerate(player_ids):
            out[i] = by_id[pid].attributes.to_row()
        return out

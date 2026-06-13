"""Player entities: attributes, players, teams, demo data.

The attribute *column contract* (`Attr`, `ATTR_COLUMNS`) is load-bearing across
layers: tactics compiles players into `(n, N_ATTR)` matrices indexed by these
columns, and the engine (and future Numba kernels) read them by integer index.
Changing column order is a breaking change to every compiled SimProgram.
"""

from restart.players.attributes import ATTR_COLUMNS, N_ATTR, Attr, PlayerAttributes
from restart.players.player import Player, PositionGroup
from restart.players.team import Team

__all__ = [
    "ATTR_COLUMNS",
    "N_ATTR",
    "Attr",
    "Player",
    "PlayerAttributes",
    "PositionGroup",
    "Team",
]

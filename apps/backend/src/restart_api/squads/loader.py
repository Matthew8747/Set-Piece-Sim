"""Build pure ``restart.Team`` squads from the committed marts (ADR-007 d2).

Reading parquet is an adapter concern; the simulation core never touches IO, so
this lives in ``restart_api`` and hands the core plain validated domain objects.

Player identities and the derived, provenance-tagged attributes come from
``mart_players`` / ``mart_player_attributes`` (StatsBomb-derived, no scraped
ratings). The marts hold a multi-match pool per nation, so an XI is selected by
a fixed, deterministic rule — registered as a simulation assumption because
attribute priors can dominate outcomes (risk R9):

* goalkeeper: the most active GK (aerial + delivery involvement as a minutes
  proxy), ties broken by player_id;
* outfield: a 4 DF / 4 MF / 2 FW shape, each bucket filled by ``heading +
  delivery`` descending (ties by player_id); buckets short of quota are topped
  up from the remaining outfielders by the same ranking.

Same marts in ⇒ same XI out (no RNG), so simulations stay reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb

from restart.players.attributes import PlayerAttributes
from restart.players.player import Player, PositionGroup
from restart.players.team import Team

PLAYERS_FILE = "mart_players.parquet"
ATTRIBUTES_FILE = "mart_player_attributes.parquet"

# mart position_group taxonomy -> engine PositionGroup. Defensive mids bolster
# the back line; wingers count as midfield (they are the usual corner takers);
# forwards/attackers are the spearheads. Documented squad-selection assumption.
_GROUP_MAP: dict[str, PositionGroup] = {
    "GK": PositionGroup.GK,
    "DEF": PositionGroup.DF,
    "DM": PositionGroup.DF,
    "MID": PositionGroup.MF,
    "WING": PositionGroup.MF,
    "FWD": PositionGroup.FW,
    "ATT": PositionGroup.FW,
}

# Outfield shape (1 GK + this = 11).
_QUOTA: dict[PositionGroup, int] = {PositionGroup.DF: 4, PositionGroup.MF: 4, PositionGroup.FW: 2}
_OUTFIELD = sum(_QUOTA.values())


def team_slug(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


@dataclass(frozen=True)
class TeamSummary:
    team_id: str  # slug
    name: str
    country: str
    n_players: int


@dataclass(frozen=True)
class _PlayerRow:
    player_id: int
    name: str
    group: PositionGroup
    activity: int  # aerial + delivery involvement (minutes proxy)
    attrs: PlayerAttributes

    @property
    def rank_key(self) -> float:
        # Higher heading + delivery first; player_id breaks ties (handled at sort).
        return self.attrs.heading + self.attrs.delivery


class MartSquadLoader:
    """Loads real squads from the marts as pure domain ``Team`` objects."""

    def __init__(self, marts_dir: Path) -> None:
        self._players = marts_dir / PLAYERS_FILE
        self._attrs = marts_dir / ATTRIBUTES_FILE
        if not self._players.is_file() or not self._attrs.is_file():
            msg = f"marts not found under {marts_dir}"
            raise FileNotFoundError(msg)
        # One in-memory connection; parquet paths are read per query. The loader
        # is a process-wide singleton AND the in-process job worker runs on a
        # threadpool, so queries go through per-call cursors — a DuckDB connection
        # is not safe to use concurrently from multiple threads, but cursors off
        # it are independent (without this, a job thread and a polling request
        # racing on the shared connection corrupt results -> "unknown team").
        self._con = duckdb.connect()
        self._players_src = f"read_parquet('{self._players.as_posix()}')"
        self._attrs_src = f"read_parquet('{self._attrs.as_posix()}')"

    # ---------------------------------------------------------------- public
    def list_teams(self) -> list[TeamSummary]:
        rows = (
            self._con.cursor()
            .execute(
                f"SELECT team, any_value(country) AS country, count(*) AS n "
                f"FROM {self._players_src} GROUP BY team ORDER BY team"
            )
            .fetchall()
        )
        return [TeamSummary(team_slug(t), t, c or "", int(n)) for t, c, n in rows]

    def team(self, name: str) -> Team:
        rows = self._load_rows(name)
        if not rows:
            msg = f"unknown team {name!r}"
            raise ValueError(msg)
        gk = self._pick_keeper(rows, name)
        outfield = self._pick_outfield([r for r in rows if r is not gk])
        players = [self._to_player(r) for r in [gk, *outfield]]
        return Team(team_id=team_slug(name), name=name, players=tuple(players))

    def team_by_id(self, team_id: str) -> Team:
        for summary in self.list_teams():
            if summary.team_id == team_id:
                return self.team(summary.name)
        msg = f"unknown team {team_id!r}"
        raise ValueError(msg)

    # --------------------------------------------------------------- internals
    def _load_rows(self, name: str) -> list[_PlayerRow]:
        cur = self._con.cursor()
        players = cur.execute(
            f"SELECT player_id, player, position_group, "
            f"COALESCE(aerial_won,0)+COALESCE(aerial_lost,0)+COALESCE(delivery_attempts,0) "
            f"AS activity FROM {self._players_src} WHERE team = ?",
            [name],
        ).fetchall()
        if not players:
            return []
        attr_rows = cur.execute(
            f"SELECT player_id, attribute, value FROM {self._attrs_src} WHERE team = ?",
            [name],
        ).fetchall()
        by_player: dict[int, dict[str, float]] = {}
        for pid, attr, value in attr_rows:
            by_player.setdefault(int(pid), {})[str(attr)] = float(value)

        rows: list[_PlayerRow] = []
        for pid, pname, group, activity in players:
            # Unknown taxonomy value -> midfield filler (keeps the XI buildable).
            mapped = _GROUP_MAP.get(str(group), PositionGroup.MF)
            rows.append(
                _PlayerRow(
                    player_id=int(pid),
                    name=str(pname),
                    group=mapped,
                    activity=int(activity),
                    attrs=PlayerAttributes(**by_player.get(int(pid), {})),
                )
            )
        return rows

    @staticmethod
    def _pick_keeper(rows: list[_PlayerRow], name: str) -> _PlayerRow:
        keepers = [r for r in rows if r.group is PositionGroup.GK]
        if not keepers:
            msg = f"team {name!r} has no goalkeeper in the marts"
            raise ValueError(msg)
        return max(keepers, key=lambda r: (r.activity, -r.player_id))

    @staticmethod
    def _pick_outfield(rows: list[_PlayerRow]) -> list[_PlayerRow]:
        outfield = [r for r in rows if r.group is not PositionGroup.GK]
        ordered = sorted(outfield, key=lambda r: (-r.rank_key, r.player_id))
        picked: list[_PlayerRow] = []
        used: set[int] = set()
        for group, quota in _QUOTA.items():
            take = [r for r in ordered if r.group is group][:quota]
            picked.extend(take)
            used.update(r.player_id for r in take)
        # Top up any quota deficit from the best remaining outfielders.
        deficit = _OUTFIELD - len(picked)
        if deficit > 0:
            topup = [r for r in ordered if r.player_id not in used][:deficit]
            picked.extend(topup)
        return picked[:_OUTFIELD]

    @staticmethod
    def _to_player(row: _PlayerRow) -> Player:
        return Player(
            player_id=str(row.player_id),
            display_name=row.name,
            position_group=row.group,
            attributes=row.attrs,
        )

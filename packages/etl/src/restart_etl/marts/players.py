"""``players`` + ``player_attributes`` marts (design doc 04 §1.3, §3).

Players come straight from lineups (real StatsBomb identities). Attributes are
*derived* with a documented method per value and provenance-tagged
``{source, method, license}`` - turning the licensing constraint (no scraped
ratings) into a credibility feature. Observable attributes (heading from aerial
duels, delivery from set-piece pass completion) are computed from events and
empirical-Bayes shrunk toward the position-group mean; the rest fall back to
position-group priors. Values are clamped to the engine's attribute bounds.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from restart_etl.marts.priors import (
    PRIOR_CURATED,
    PRIOR_LITERATURE,
    group_prior,
    position_group,
)

PLAYERS_FILE = "mart_players.parquet"
ATTRIBUTES_FILE = "mart_player_attributes.parquet"

# Engine attribute bounds (mirror restart.players.attributes; clamp on emit).
_BOUNDS: dict[str, tuple[float, float]] = {
    "top_speed_ms": (5.5, 9.8),
    "accel_ms2": (2.0, 8.0),
    "reaction_time_s": (0.15, 0.45),
    "agility": (0.0, 1.0),
    "jump_reach_m": (2.10, 3.00),
    "heading": (0.0, 1.0),
    "strength": (0.0, 1.0),
    "marking": (0.0, 1.0),
    "awareness_off": (0.0, 1.0),
    "awareness_def": (0.0, 1.0),
    "delivery": (0.0, 1.0),
    "height_m": (1.60, 2.10),
}
_UNITS: dict[str, str] = {
    "top_speed_ms": "m/s",
    "accel_ms2": "m/s^2",
    "reaction_time_s": "s",
    "jump_reach_m": "m",
    "height_m": "m",
}

# Licenses by provenance class.
_SB_DERIVED = "StatsBomb Open Data (derived, attribution required)"
_LIT = "n/a (literature prior)"
_CURATED = "n/a (analyst curated)"

# Shrinkage strengths (prior-equivalent sample size).
_K_AERIAL = 8.0
_K_DELIVERY = 6.0
_MIN_DELIVERY_ATTEMPTS = 4


def _clamp(name: str, value: float) -> float:
    lo, hi = _BOUNDS[name]
    return max(lo, min(hi, value))


@dataclass
class PlayerAgg:
    player_id: int
    player: str = ""
    team: str = ""
    team_id: int = 0
    country: str = ""
    positions: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    aerial_won: int = 0  # head contacts in pass/shot/clearance (success proxy)
    aerial_lost: int = 0  # Duel / Aerial Lost
    delivery_total: int = 0  # corner/FK/cross passes attempted
    delivery_complete: int = 0


class PlayerAccumulator:
    """Accumulates per-player identity, position, and event aggregates."""

    def __init__(self) -> None:
        self._agg: dict[int, PlayerAgg] = {}

    def _get(self, pid: int) -> PlayerAgg:
        a = self._agg.get(pid)
        if a is None:
            a = PlayerAgg(player_id=pid)
            self._agg[pid] = a
        return a

    def observe_lineup(self, lineups: list[dict[str, Any]]) -> None:
        for team in lineups:
            tname = str(team.get("team_name", ""))
            tid = int(team.get("team_id", 0))
            for pl in team.get("lineup", []):
                pid = int(pl["player_id"])
                a = self._get(pid)
                a.player = str(pl.get("player_nickname") or pl.get("player_name") or "")
                a.team = tname
                a.team_id = tid
                a.country = str(pl.get("country", {}).get("name", "")) if pl.get("country") else ""
                for pos in pl.get("positions", []):
                    name = pos.get("position")
                    if name:
                        a.positions[name] += 1

    def observe_event(self, event: dict[str, Any]) -> None:
        player = event.get("player")
        if not player:
            return
        pid = int(player["id"])
        a = self._get(pid)
        etype = event.get("type", {}).get("name", "")

        if etype == "Duel" and event.get("duel", {}).get("type", {}).get("name") == "Aerial Lost":
            a.aerial_lost += 1
            return
        if etype in ("Pass", "Shot", "Clearance"):
            body = event.get(etype.lower(), {}).get("body_part", {}).get("name")
            if body == "Head":
                a.aerial_won += 1
        if etype == "Pass":
            p = event["pass"]
            ptype = p.get("type", {}).get("name", "")
            is_delivery = bool(p.get("cross")) or ptype in ("Corner", "Free Kick")
            if is_delivery:
                a.delivery_total += 1
                if p.get("outcome") is None:  # StatsBomb marks only failures
                    a.delivery_complete += 1

    # ----------------------------------------------------------- finalize
    def _primary_position(self, a: PlayerAgg) -> str:
        if not a.positions:
            return "Center Midfield"
        return max(a.positions.items(), key=lambda kv: kv[1])[0]

    def finalize(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        players: list[dict[str, Any]] = []
        attributes: list[dict[str, Any]] = []
        for a in sorted(self._agg.values(), key=lambda x: x.player_id):
            if not a.player:
                continue
            position = self._primary_position(a)
            group = position_group(position)
            players.append(
                {
                    "player_id": a.player_id,
                    "player": a.player,
                    "team": a.team,
                    "team_id": a.team_id,
                    "country": a.country,
                    "primary_position": position,
                    "position_group": group,
                    "aerial_won": a.aerial_won,
                    "aerial_lost": a.aerial_lost,
                    "delivery_attempts": a.delivery_total,
                    "source": "statsbomb_open_data",
                }
            )
            attributes.extend(self._derive(a, group))
        return players, attributes

    def _emit(
        self, a: PlayerAgg, attribute: str, value: float, source: str, method: str, license: str
    ) -> dict[str, Any]:
        return {
            "player_id": a.player_id,
            "player": a.player,
            "team": a.team,
            "attribute": attribute,
            "value": round(_clamp(attribute, value), 4),
            "unit": _UNITS.get(attribute, "0-1"),
            "source": source,
            "method": method,
            "license": license,
        }

    def _derive(self, a: PlayerAgg, group: str) -> list[dict[str, Any]]:
        prior = group_prior(group)
        vjump = prior.pop("vertical_m")
        rows: list[dict[str, Any]] = []

        # heading: aerial win rate (head contacts vs aerial-lost), EB-shrunk.
        aerial_n = a.aerial_won + a.aerial_lost
        if aerial_n > 0:
            rate = a.aerial_won / aerial_n
            heading = (aerial_n * rate + _K_AERIAL * prior["heading"]) / (aerial_n + _K_AERIAL)
            rows.append(
                self._emit(
                    a,
                    "heading",
                    heading,
                    "derived",
                    f"aerial win rate {a.aerial_won}/{aerial_n}, EB-shrunk (k={_K_AERIAL:g}) "
                    f"to {group} prior",
                    _SB_DERIVED,
                )
            )
        else:
            rows.append(
                self._emit(
                    a,
                    "heading",
                    prior["heading"],
                    "literature_prior",
                    f"{group} position prior (no aerial sample)",
                    _LIT,
                )
            )

        # delivery: set-piece/cross completion, EB-shrunk; prior if sparse.
        if a.delivery_total >= _MIN_DELIVERY_ATTEMPTS:
            rate = a.delivery_complete / a.delivery_total
            deliv = (a.delivery_total * rate + _K_DELIVERY * prior["delivery"]) / (
                a.delivery_total + _K_DELIVERY
            )
            rows.append(
                self._emit(
                    a,
                    "delivery",
                    deliv,
                    "derived",
                    f"set-piece/cross completion {a.delivery_complete}/{a.delivery_total}, "
                    f"EB-shrunk (k={_K_DELIVERY:g})",
                    _SB_DERIVED,
                )
            )
        else:
            rows.append(
                self._emit(
                    a,
                    "delivery",
                    prior["delivery"],
                    "literature_prior",
                    f"{group} position prior (delivery sample < {_MIN_DELIVERY_ATTEMPTS})",
                    _LIT,
                )
            )

        # height + jump_reach (derived from height + position vertical prior).
        height = prior["height_m"]
        rows.append(
            self._emit(
                a,
                "height_m",
                height,
                "literature_prior",
                f"{group} anthropometric prior (no licensed height source)",
                _LIT,
            )
        )
        jump_reach = 1.25 * height + vjump
        rows.append(
            self._emit(
                a,
                "jump_reach_m",
                jump_reach,
                "derived",
                f"standing reach (1.25*height) + {group} vertical-jump prior ({vjump:g} m)",
                _SB_DERIVED,
            )
        )

        # remaining attributes: literature or curated priors.
        for name in ("top_speed_ms", "accel_ms2", "reaction_time_s"):
            rows.append(
                self._emit(
                    a,
                    name,
                    prior[name],
                    "literature_prior",
                    f"{group} sprint/reaction-time literature prior",
                    _LIT,
                )
            )
        for name in ("agility", "strength", "marking", "awareness_off", "awareness_def"):
            cls = "literature_prior" if name in PRIOR_LITERATURE else "curated"
            lic = _LIT if name in PRIOR_LITERATURE else _CURATED
            tag = "literature prior" if name in PRIOR_LITERATURE else "analyst-curated prior"
            assert name in PRIOR_CURATED or name in PRIOR_LITERATURE
            rows.append(self._emit(a, name, prior[name], cls, f"{group} {tag}", lic))
        return rows

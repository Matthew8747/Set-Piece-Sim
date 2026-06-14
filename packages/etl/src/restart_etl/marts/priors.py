"""Position-group attribute priors (the honest fallback, design doc 04 §3).

There is no licensed source of game-style ratings, so non-observable attributes
default to position-group priors drawn from the sprint/reaction-time literature
(see restart.players.attributes docstring) and explicit analyst curation. Every
prior is provenance-tagged at emission so the UI badge can say *why* a value is
what it is. Observable attributes (heading, delivery) override these from event
data where the sample supports it.
"""

from __future__ import annotations

from typing import Final

# Coarse position groups derived from StatsBomb position names.
GK = "GK"
DEF = "DEF"
DM = "DM"
MID = "MID"
ATT = "ATT"
WING = "WING"
FWD = "FWD"

_POSITION_GROUP: Final[dict[str, str]] = {
    "Goalkeeper": GK,
    "Right Back": DEF,
    "Left Back": DEF,
    "Right Center Back": DEF,
    "Left Center Back": DEF,
    "Center Back": DEF,
    "Right Wing Back": WING,
    "Left Wing Back": WING,
    "Center Defensive Midfield": DM,
    "Right Defensive Midfield": DM,
    "Left Defensive Midfield": DM,
    "Right Center Midfield": MID,
    "Left Center Midfield": MID,
    "Center Midfield": MID,
    "Right Midfield": MID,
    "Left Midfield": MID,
    "Center Attacking Midfield": ATT,
    "Right Attacking Midfield": ATT,
    "Left Attacking Midfield": ATT,
    "Right Wing": WING,
    "Left Wing": WING,
    "Secondary Striker": FWD,
    "Center Forward": FWD,
    "Right Center Forward": FWD,
    "Left Center Forward": FWD,
}


def position_group(position: str) -> str:
    return _POSITION_GROUP.get(position, MID)


# Per-group priors for the 12 engine attributes. Values sit inside
# restart.players.attributes bounds; heading/delivery are starting points that
# event data refines. height_m drives jump_reach via standing reach + vertical.
# (top_speed/accel: sprint literature; height: position-group anthropometric
# averages for elite men's football.)
_PRIORS: Final[dict[str, dict[str, float]]] = {
    GK: {
        "top_speed_ms": 7.4,
        "accel_ms2": 4.5,
        "reaction_time_s": 0.22,
        "agility": 0.45,
        "heading": 0.45,
        "strength": 0.60,
        "marking": 0.40,
        "awareness_off": 0.30,
        "awareness_def": 0.65,
        "delivery": 0.45,
        "height_m": 1.90,
        "vertical_m": 0.55,
    },
    DEF: {
        "top_speed_ms": 8.2,
        "accel_ms2": 5.2,
        "reaction_time_s": 0.24,
        "agility": 0.55,
        "heading": 0.62,
        "strength": 0.65,
        "marking": 0.65,
        "awareness_off": 0.40,
        "awareness_def": 0.62,
        "delivery": 0.42,
        "height_m": 1.86,
        "vertical_m": 0.58,
    },
    DM: {
        "top_speed_ms": 8.2,
        "accel_ms2": 5.3,
        "reaction_time_s": 0.24,
        "agility": 0.58,
        "heading": 0.52,
        "strength": 0.58,
        "marking": 0.58,
        "awareness_off": 0.50,
        "awareness_def": 0.58,
        "delivery": 0.55,
        "height_m": 1.81,
        "vertical_m": 0.56,
    },
    MID: {
        "top_speed_ms": 8.3,
        "accel_ms2": 5.5,
        "reaction_time_s": 0.23,
        "agility": 0.62,
        "heading": 0.48,
        "strength": 0.52,
        "marking": 0.50,
        "awareness_off": 0.58,
        "awareness_def": 0.52,
        "delivery": 0.60,
        "height_m": 1.79,
        "vertical_m": 0.57,
    },
    ATT: {
        "top_speed_ms": 8.5,
        "accel_ms2": 5.7,
        "reaction_time_s": 0.22,
        "agility": 0.68,
        "heading": 0.48,
        "strength": 0.48,
        "marking": 0.38,
        "awareness_off": 0.66,
        "awareness_def": 0.42,
        "delivery": 0.62,
        "height_m": 1.78,
        "vertical_m": 0.58,
    },
    WING: {
        "top_speed_ms": 8.9,
        "accel_ms2": 6.0,
        "reaction_time_s": 0.22,
        "agility": 0.70,
        "heading": 0.45,
        "strength": 0.46,
        "marking": 0.45,
        "awareness_off": 0.62,
        "awareness_def": 0.48,
        "delivery": 0.58,
        "height_m": 1.78,
        "vertical_m": 0.59,
    },
    FWD: {
        "top_speed_ms": 8.6,
        "accel_ms2": 5.8,
        "reaction_time_s": 0.22,
        "agility": 0.64,
        "heading": 0.58,
        "strength": 0.58,
        "marking": 0.35,
        "awareness_off": 0.64,
        "awareness_def": 0.40,
        "delivery": 0.50,
        "height_m": 1.84,
        "vertical_m": 0.60,
    },
}


def group_prior(group: str) -> dict[str, float]:
    return dict(_PRIORS.get(group, _PRIORS[MID]))


# Which attributes are pure priors vs literature-vs-curated, for provenance.
PRIOR_LITERATURE = frozenset({"top_speed_ms", "accel_ms2", "reaction_time_s", "height_m"})
PRIOR_CURATED = frozenset({"agility", "strength", "marking", "awareness_off", "awareness_def"})

"""Attribute sensitivity analysis (data-pipeline doc 04 sec3 guardrail).

Curated player attributes are priors, not measurements (ADR-005). If perturbing
them +/-10% reshuffles the optimizer's routine ranking, then the discovery is a
statement about *that exact squad*, and we must report routine **classes**
("near-post inswingers beat this zonal line") rather than player-precise
prescriptions (roadmap R9). This module provides the attribute perturbation and
the ranking-stability decision; the engine-backed evaluation is wired in
``canonical.py``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from restart.players.attributes import PlayerAttributes
from restart.players.player import Player
from restart.players.team import Team

#: Curated/derived attributes (doc 04 sec3) + their plausibility bounds for
#: clamping after scaling. These are the priors whose influence we stress-test.
CURATED_BOUNDS: dict[str, tuple[float, float]] = {
    "heading": (0.0, 1.0),
    "strength": (0.0, 1.0),
    "delivery": (0.0, 1.0),
    "jump_reach_m": (2.10, 3.00),
    "marking": (0.0, 1.0),
}
CURATED_FIELDS: tuple[str, ...] = tuple(CURATED_BOUNDS)


def scale_attributes(
    attrs: PlayerAttributes, frac: float, fields: Sequence[str] = CURATED_FIELDS
) -> PlayerAttributes:
    """Return attrs with ``fields`` scaled by ``(1 + frac)``, clamped to bounds."""
    updates: dict[str, float] = {}
    for name in fields:
        lo, hi = CURATED_BOUNDS[name]
        scaled = float(getattr(attrs, name)) * (1.0 + frac)
        updates[name] = min(hi, max(lo, scaled))
    return attrs.model_copy(update=updates)


def perturb_team(team: Team, frac: float, fields: Sequence[str] = CURATED_FIELDS) -> Team:
    """Return a copy of ``team`` with every player's curated attributes scaled."""
    players: list[Player] = [
        p.model_copy(update={"attributes": scale_attributes(p.attributes, frac, fields)})
        for p in team.players
    ]
    return team.model_copy(update={"players": tuple(players)})


@dataclass(frozen=True, slots=True)
class SensitivityResult:
    top1_stable: bool
    rankings_flip: bool
    verdict: str  # "routine-precise" | "report-routine-classes"
    baseline_order: list[str]
    flipped: list[str] = field(default_factory=list)


def rank_stability(
    baseline: Mapping[str, float],
    perturbed: Mapping[str, Mapping[str, float]],
) -> SensitivityResult:
    """Decide routine-precise vs report-classes from perturbed re-rankings.

    ``baseline`` maps candidate id -> score; ``perturbed`` maps a perturbation
    label -> (candidate id -> score). The discovery is precise only if the
    best candidate stays best under every perturbation.
    """
    base_order = sorted(baseline, key=lambda k: baseline[k], reverse=True)
    base_top1 = base_order[0]
    flipped: list[str] = []
    for label, scores in perturbed.items():
        order = sorted(scores, key=lambda k: scores[k], reverse=True)
        if order and order[0] != base_top1:
            flipped.append(label)
    top1_stable = not flipped
    return SensitivityResult(
        top1_stable=top1_stable,
        rankings_flip=bool(flipped),
        verdict="routine-precise" if top1_stable else "report-routine-classes",
        baseline_order=base_order,
        flipped=flipped,
    )

"""Outcome aggregation: probabilities with Wilson 95% CIs (M-2).

SciPy's ``binomtest(...).proportion_ci(method="wilson")`` per ADR-001 —
statistics are bought, not built.
"""

from dataclasses import dataclass

from scipy.stats import binomtest

from restart.montecarlo.runner import BatchResult
from restart.simulation.events import (
    FirstContactEvent,
    SetPieceOutcome,
    ShotEvent,
)


@dataclass(frozen=True, slots=True)
class ProportionCI:
    """A proportion with its Wilson 95% interval."""

    p: float
    lo: float
    hi: float
    k: int  # successes
    n: int  # trials


def wilson(k: int, n: int) -> ProportionCI:
    if n == 0:
        return ProportionCI(p=0.0, lo=0.0, hi=1.0, k=0, n=0)
    ci = binomtest(k, n).proportion_ci(method="wilson")
    return ProportionCI(p=k / n, lo=float(ci.low), hi=float(ci.high), k=k, n=n)


@dataclass(frozen=True, slots=True)
class OutcomeStats:
    """The PRD FR-4.2 metric set for one batch."""

    n_sims: int
    p_goal: ProportionCI
    p_shot: ProportionCI
    p_header_shot: ProportionCI
    p_first_contact_attack: ProportionCI
    p_clearance: ProportionCI
    p_possession_recovered: ProportionCI  # attack keeps/regains the ball
    outcome_counts: dict[str, int]
    # Mean scored xG per simulation (doc 06 §2.3): 0 contributed by sims without
    # a shot, and by shots scored before an xG model was wired (xg is None).
    mean_xg: float
    # How many shots actually carried an xG score (xg is not None).
    n_xg_scored: int


def aggregate(batch: BatchResult) -> OutcomeStats:
    n = batch.n_sims
    goals = shots = headers = fc_attack = clearances = recovered = 0
    xg_sum = 0.0
    n_xg_scored = 0
    counts: dict[str, int] = {}

    for r in batch.results:
        counts[r.outcome.value] = counts.get(r.outcome.value, 0) + 1
        if r.outcome is SetPieceOutcome.GOAL:
            goals += 1
        if r.outcome is SetPieceOutcome.CLEARED:
            clearances += 1
        if r.outcome in (SetPieceOutcome.GOAL, SetPieceOutcome.SECOND_BALL_ATTACK):
            recovered += 1
        shot = next((e for e in r.events if isinstance(e, ShotEvent)), None)
        if shot is not None:
            shots += 1
            if shot.is_header:
                headers += 1
            if shot.xg is not None:
                xg_sum += shot.xg
                n_xg_scored += 1
        fc = next((e for e in r.events if isinstance(e, FirstContactEvent)), None)
        if fc is not None and fc.team == "attack":
            fc_attack += 1

    return OutcomeStats(
        n_sims=n,
        p_goal=wilson(goals, n),
        p_shot=wilson(shots, n),
        p_header_shot=wilson(headers, n),
        p_first_contact_attack=wilson(fc_attack, n),
        p_clearance=wilson(clearances, n),
        p_possession_recovered=wilson(recovered, n),
        outcome_counts=counts,
        mean_xg=(xg_sum / n if n else 0.0),
        n_xg_scored=n_xg_scored,
    )

"""Anti-exploit guards (pure): flag optimizer discoveries that smell like
simulator exploits rather than football insight.

Optimizers find simulator bugs before they find football insights (doc 06
sec3.2). Two cheap, rule-based screens feed the face-validity review of the
top-k: (1) parameters pinned within epsilon of a search bound (the optimizer is
riding a wall, often a model edge), and (2) an implausibly high objective (real
corner mean xG is far below the ceiling - a high value signals a degenerate
strike geometry the engine over-rewards).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from restart.optimize.genome import ContinuousParam, IntParam, SearchSpace


def boundary_flags(
    space: SearchSpace, values: Mapping[str, object], eps_frac: float = 0.02
) -> list[str]:
    """Names of numeric params sitting within ``eps_frac`` of a bound.

    Categoricals are skipped (no notion of "near a bound"). ``eps_frac`` is a
    fraction of each param's range.
    """
    flags: list[str] = []
    for p in space.params:
        if not isinstance(p, ContinuousParam | IntParam):
            continue
        if p.name not in values:
            continue
        v = float(values[p.name])  # type: ignore[arg-type]
        span = float(p.hi - p.lo)
        if span <= 0:
            continue
        eps = eps_frac * span
        if v <= p.lo + eps or v >= p.hi - eps:
            flags.append(p.name)
    return flags


def face_validity_flags(
    mean_xg: float,
    boundary: Sequence[str] = (),
    mean_xg_ceiling: float = 0.5,
) -> list[str]:
    """Plain-language face-validity warnings for a candidate (empty == clean)."""
    flags: list[str] = []
    if mean_xg > mean_xg_ceiling:
        flags.append(
            f"implausible mean_xg={mean_xg:.3f} > ceiling {mean_xg_ceiling:.2f} "
            f"(likely a simulator exploit, not a football insight)"
        )
    if boundary:
        flags.append(f"parameters pinned at search bounds: {sorted(boundary)}")
    return flags

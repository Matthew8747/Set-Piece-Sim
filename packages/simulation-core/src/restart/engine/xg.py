"""Expected-goals scoring contract for the simulator (pure domain).

The engine emits a :class:`ShotContext` (geometry + traffic at the strike); a
:class:`XGScorer` turns it into a calibrated P(goal). This module is the *single
source of truth* for the xG feature surface — the training package (restart_ml)
builds its design matrix by constructing the same :class:`ShotContext` from real
shots and calling :func:`shot_feature_vector`, so train-time and score-time
features are identical quantities (design doc 06 §2.3).

Purity (the dependency rule): this is closed-form NumPy/math only — no sklearn,
no file I/O. The shipped logistic model lives here as plain coefficients loaded
from a dict; gradient-boosted alternatives, if they win the calibration bake-off,
are injected from the adapter via the :class:`XGScorer` protocol. Either way the
core stays pure and the engine never imports an ML framework.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

# Candidate feature surface (closed-form so the pure scorer reproduces training
# exactly). A model's artifact names the subset it actually uses; the scorer
# selects those names from this dict. Append-only by convention.
FEATURE_NAMES: tuple[str, ...] = (
    "distance",
    "inv_distance",
    "distance_sq",
    "log_distance",
    "angle",
    "angle_sq",
    "is_header",
    "defenders_in_cone",
    "nearest_def_dist",
    "defenders_within_3m",
    "gk_dist_to_goal",
    "gk_lateral",
    "under_pressure",
    "phase_first_contact",
    "phase_second_ball",
    "header_x_distance",
    "cone_x_inv_distance",
)


@dataclass(frozen=True, slots=True)
class ShotContext:
    """Geometry + traffic at a shot, in the canonical metric frame.

    Mirrors ``mart_setpiece_shots`` columns so a real shot row and a simulated
    strike map to the same features.
    """

    distance_m: float
    angle_rad: float
    is_header: bool
    set_piece_phase: str  # 'direct' | 'first_contact' | 'second_ball'
    defenders_in_cone: int
    nearest_def_dist_m: float
    defenders_within_3m: int
    gk_dist_to_goal_m: float
    gk_lateral_m: float
    under_pressure: bool


def shot_feature_vector(ctx: ShotContext) -> dict[str, float]:
    """Closed-form feature expansion shared by training and scoring."""
    d = max(0.0, ctx.distance_m)
    a = ctx.angle_rad
    is_header = 1.0 if ctx.is_header else 0.0
    inv_d = 1.0 / (d + 0.5)
    return {
        "distance": d,
        "inv_distance": inv_d,
        "distance_sq": d * d,
        "log_distance": math.log1p(d),
        "angle": a,
        "angle_sq": a * a,
        "is_header": is_header,
        "defenders_in_cone": float(ctx.defenders_in_cone),
        "nearest_def_dist": min(float(ctx.nearest_def_dist_m), 20.0),
        "defenders_within_3m": float(ctx.defenders_within_3m),
        "gk_dist_to_goal": float(ctx.gk_dist_to_goal_m),
        "gk_lateral": float(ctx.gk_lateral_m),
        "under_pressure": 1.0 if ctx.under_pressure else 0.0,
        "phase_first_contact": 1.0 if ctx.set_piece_phase == "first_contact" else 0.0,
        "phase_second_ball": 1.0 if ctx.set_piece_phase == "second_ball" else 0.0,
        "header_x_distance": is_header * d,
        "cone_x_inv_distance": float(ctx.defenders_in_cone) * inv_d,
    }


@runtime_checkable
class XGScorer(Protocol):
    """Anything that turns a :class:`ShotContext` into a calibrated P(goal)."""

    def score(self, context: ShotContext) -> float: ...


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def _apply_calibration(p: float, calib: dict[str, Any] | None) -> float:
    """Post-hoc calibration map (Platt or isotonic), embedded in the artifact."""
    if not calib:
        return p
    kind = calib.get("type")
    if kind == "platt":
        # Platt: sigmoid(a * logit-ish-score + b). Here we calibrate on the raw
        # probability's logit for a stable 2-parameter map.
        a = float(calib["a"])
        b = float(calib["b"])
        eps = 1e-6
        pc = min(max(p, eps), 1 - eps)
        logit = math.log(pc / (1 - pc))
        return _sigmoid(a * logit + b)
    if kind == "isotonic":
        xs = calib["x"]
        ys = calib["y"]
        # Piecewise-linear interpolation of the isotonic step function.
        if p <= xs[0]:
            return float(ys[0])
        if p >= xs[-1]:
            return float(ys[-1])
        for i in range(1, len(xs)):
            if p <= xs[i]:
                x0, x1 = xs[i - 1], xs[i]
                y0, y1 = ys[i - 1], ys[i]
                t = 0.0 if x1 == x0 else (p - x0) / (x1 - x0)
                return float(y0 + t * (y1 - y0))
    return p


@dataclass(frozen=True, slots=True)
class LogisticXGScorer:
    """Pure logistic xG model: sigmoid(intercept + coef . features), calibrated."""

    model_id: str
    feature_names: tuple[str, ...]
    coef: tuple[float, ...]
    intercept: float
    calibration: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if len(self.feature_names) != len(self.coef):
            raise ValueError(
                f"{self.model_id}: {len(self.feature_names)} names vs {len(self.coef)} coefs"
            )

    def score(self, context: ShotContext) -> float:
        feats = shot_feature_vector(context)
        z = self.intercept
        for name, c in zip(self.feature_names, self.coef, strict=True):
            z += c * feats[name]
        return _apply_calibration(_sigmoid(z), self.calibration)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "feature_names": list(self.feature_names),
            "coef": list(self.coef),
            "intercept": self.intercept,
            "calibration": self.calibration,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LogisticXGScorer:
        return cls(
            model_id=str(d["model_id"]),
            feature_names=tuple(d["feature_names"]),
            coef=tuple(float(c) for c in d["coef"]),
            intercept=float(d["intercept"]),
            calibration=d.get("calibration"),
        )


@dataclass(frozen=True, slots=True)
class XGModelBundle:
    """Routes a shot to the header or foot model by body part (doc 06 §2.1)."""

    header: XGScorer
    foot: XGScorer
    bundle_id: str = "xg-v1"

    def score(self, context: ShotContext) -> float:
        scorer = self.header if context.is_header else self.foot
        return scorer.score(context)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> XGModelBundle:
        return cls(
            header=LogisticXGScorer.from_dict(d["header"]),
            foot=LogisticXGScorer.from_dict(d["foot"]),
            bundle_id=str(d.get("bundle_id", "xg-v1")),
        )

    def to_dict(self) -> dict[str, Any]:
        header = self.header
        foot = self.foot
        if not isinstance(header, LogisticXGScorer) or not isinstance(foot, LogisticXGScorer):
            raise TypeError("to_dict requires LogisticXGScorer members")
        return {
            "bundle_id": self.bundle_id,
            "header": header.to_dict(),
            "foot": foot.to_dict(),
        }

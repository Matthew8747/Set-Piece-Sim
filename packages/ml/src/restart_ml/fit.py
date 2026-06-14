"""Fit the shipped logistic xG model into a pure, engine-loadable scorer.

The model is trained as ``StandardScaler -> LogisticRegression`` for numerical
conditioning, then the standardization is *folded into raw coefficients* so the
simulation core's :class:`LogisticXGScorer` can apply them directly to the
closed-form features — no scaler, no sklearn at score time. Calibration is a
Platt map fit on out-of-fold probabilities, embedded in the artifact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from restart.engine.xg import LogisticXGScorer
from restart_ml.data import Dataset
from restart_ml.evaluate import calibration_slope_intercept, cross_val_oof, oof_metrics
from restart_ml.models import make_logreg


def _fold_standardization(
    coef: np.ndarray, intercept: float, mean: np.ndarray, scale: np.ndarray
) -> tuple[list[float], float]:
    """Map standardized-feature coefficients to raw-feature coefficients."""
    raw_coef = coef / scale
    raw_intercept = intercept - float(np.sum(coef * mean / scale))
    return [float(c) for c in raw_coef], float(raw_intercept)


@dataclass(frozen=True, slots=True)
class FittedModel:
    scorer: LogisticXGScorer
    metrics_uncalibrated: dict[str, float]
    metrics_calibrated: dict[str, float]


def fit_logistic_scorer(dataset: Dataset, *, n_splits: int = 5) -> FittedModel:
    """Fit the calibrated logistic scorer for one body-part split."""
    pipe = make_logreg()
    pipe.fit(dataset.x, dataset.y)
    scaler = pipe.named_steps["scale"]
    clf = pipe.named_steps["clf"]
    raw_coef, raw_intercept = _fold_standardization(
        clf.coef_[0], float(clf.intercept_[0]), scaler.mean_, scaler.scale_
    )

    # Honest calibration: fit Platt on out-of-fold probabilities, not in-sample.
    oof, metrics_uncal = cross_val_oof(
        make_logreg, dataset.x, dataset.y, dataset.groups, n_splits=n_splits
    )
    calibration: dict[str, Any] | None = None
    metrics_cal = dict(metrics_uncal)
    mask = ~np.isnan(oof)
    if mask.sum() > 0 and len(np.unique(dataset.y[mask])) >= 2:
        a, b = calibration_slope_intercept(dataset.y[mask], np.clip(oof[mask], 1e-6, 1 - 1e-6))
        if np.isfinite(a) and np.isfinite(b):
            calibration = {"type": "platt", "a": a, "b": b}
            # Recompute calibrated OOF metrics for the model card.
            calibrated_oof = _apply_platt(oof, a, b)
            metrics_cal = oof_metrics(dataset.y, calibrated_oof)

    scorer = LogisticXGScorer(
        model_id=dataset.model_id,
        feature_names=dataset.feature_names,
        coef=tuple(raw_coef),
        intercept=raw_intercept,
        calibration=calibration,
    )
    return FittedModel(
        scorer=scorer,
        metrics_uncalibrated=metrics_uncal,
        metrics_calibrated=metrics_cal,
    )


def _apply_platt(p: np.ndarray, a: float, b: float) -> np.ndarray:
    pc = np.clip(p, 1e-6, 1 - 1e-6)
    logit = np.log(pc / (1 - pc))
    out: np.ndarray = 1.0 / (1.0 + np.exp(-(a * logit + b)))
    return out

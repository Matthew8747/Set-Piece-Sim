"""Leakage-safe evaluation: grouped-by-match CV with calibration metrics.

Shots from one match never straddle a fold (``GroupKFold`` on ``match_id``) — the
leakage guard from design doc 06 §2.2. For a model whose output feeds
expectations, the metric that matters is calibration: we report the calibration
slope/intercept (a logistic of the outcome on the predicted logit; slope ~ 1,
intercept ~ 0 is well-calibrated) alongside log-loss, Brier, and AUC.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold

FloatArr = npt.NDArray[np.float64]
IntArr = npt.NDArray[np.int64]

_EPS = 1e-6


def _logit(p: FloatArr) -> FloatArr:
    pc = np.clip(p, _EPS, 1 - _EPS)
    return np.log(pc / (1 - pc))


def calibration_slope_intercept(y: IntArr, p: FloatArr) -> tuple[float, float]:
    """Fit logit(outcome) ~ a*logit(p) + b; return (slope a, intercept b)."""
    if len(np.unique(y)) < 2:
        return float("nan"), float("nan")
    lr = LogisticRegression(C=1e6, max_iter=1000)
    lr.fit(_logit(p).reshape(-1, 1), y)
    return float(lr.coef_[0][0]), float(lr.intercept_[0])


def cross_val_oof(
    factory: Any,
    x: FloatArr,
    y: IntArr,
    groups: IntArr,
    n_splits: int = 5,
) -> tuple[FloatArr, dict[str, float]]:
    """Return (out-of-fold probabilities, aggregate metrics) for one candidate."""
    n_groups = len(np.unique(groups))
    splits = max(2, min(n_splits, n_groups))
    oof = np.full(len(y), np.nan, dtype=np.float64)
    gkf = GroupKFold(n_splits=splits)
    for train_idx, test_idx in gkf.split(x, y, groups):
        if len(np.unique(y[train_idx])) < 2:
            continue
        model = factory()
        model.fit(x[train_idx], y[train_idx])
        proba = model.predict_proba(x[test_idx])[:, 1]
        oof[test_idx] = proba
    return oof, oof_metrics(y, oof)


def oof_metrics(y: IntArr, oof: FloatArr) -> dict[str, float]:
    mask = ~np.isnan(oof)
    yv = y[mask]
    pv = np.clip(oof[mask], _EPS, 1 - _EPS)
    if len(yv) == 0 or len(np.unique(yv)) < 2:
        return {
            "n": float(len(yv)),
            "log_loss": float("nan"),
            "brier": float("nan"),
            "auc": float("nan"),
            "cal_slope": float("nan"),
            "cal_intercept": float("nan"),
            "base_rate": float(yv.mean()) if len(yv) else 0.0,
        }
    slope, intercept = calibration_slope_intercept(yv, pv)
    return {
        "n": float(len(yv)),
        "log_loss": float(log_loss(yv, pv)),
        "brier": float(brier_score_loss(yv, pv)),
        "auc": float(roc_auc_score(yv, pv)),
        "cal_slope": slope,
        "cal_intercept": intercept,
        "base_rate": float(yv.mean()),
    }

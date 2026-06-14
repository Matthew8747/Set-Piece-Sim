"""Candidate model registry for the xG method comparison (design doc 06 §2.2).

Logistic regression is the mandatory baseline; gradient-boosted machines and a
random forest are the challengers. All expose the sklearn ``predict_proba`` API,
so the grouped-CV harness treats them uniformly. Boosting libraries are imported
lazily and skipped (not failed) if unavailable, so the sweep degrades gracefully.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ModelFactory = Callable[[], Any]


def make_logreg() -> Any:
    """Splined-spirit logistic baseline: standardized features + L2 logistic."""
    return Pipeline(
        steps=[
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(C=1.0, max_iter=2000, class_weight=None)),
        ]
    )


def make_hist_gbm() -> Any:
    return HistGradientBoostingClassifier(
        max_depth=3, learning_rate=0.05, max_iter=300, l2_regularization=1.0
    )


def make_random_forest() -> Any:
    return RandomForestClassifier(
        n_estimators=300, max_depth=6, min_samples_leaf=20, n_jobs=1, random_state=0
    )


def candidate_models() -> dict[str, ModelFactory]:
    """All candidates available in this environment (key -> factory)."""
    models: dict[str, ModelFactory] = {
        "logreg": make_logreg,
        "hist_gbm": make_hist_gbm,
        "random_forest": make_random_forest,
    }
    try:
        from xgboost import XGBClassifier

        models["xgboost"] = lambda: XGBClassifier(
            n_estimators=300,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            eval_metric="logloss",
            n_jobs=1,
            verbosity=0,
        )
    except ImportError:  # pragma: no cover
        pass
    try:
        from lightgbm import LGBMClassifier

        models["lightgbm"] = lambda: LGBMClassifier(
            n_estimators=300,
            max_depth=3,
            num_leaves=15,
            learning_rate=0.05,
            subsample=0.8,
            reg_lambda=1.0,
            n_jobs=1,
            verbose=-1,
        )
    except ImportError:  # pragma: no cover
        pass
    return models

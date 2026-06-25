"""Surrogate model + SHAP insights (design doc 06 sec3.3).

After a study accumulates trials, fit a LightGBM regressor on
(routine params -> mean xG) and run SHAP on it to answer "what makes a good
corner against this defense?". The surrogate is an *explanation* of the trials,
not a replacement for the simulator - its job is to turn the trial cloud into a
few plain-language findings a coach could act on (the differentiating UI panel).

Encoding is pandas-free (the project avoids pandas under mypy --strict):
continuous params pass through; categoricals are integer-coded with their indices
declared to LightGBM, and SHAP attributes importance per original feature.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import shap

from restart.domain.vectors import FloatArray
from restart.optimize.genome import CategoricalParam, ContinuousParam, IntParam, SearchSpace
from restart_opt.study import TrialRecord

_MIN_TRIALS = 10  # below this, SHAP on a tree model is noise, not insight


@dataclass(frozen=True, slots=True)
class SurrogateResult:
    feature_importance: dict[str, float]  # mean |SHAP| per feature
    insights: list[str]  # plain-language findings, strongest first
    n_trials: int
    feature_names: list[str] = field(default_factory=list)


def _encode(
    space: SearchSpace, trials: Sequence[TrialRecord]
) -> tuple[FloatArray, FloatArray, list[int], dict[str, dict[int, str]]]:
    """Return (X, y, categorical_col_indices, {feat: {code: label}})."""
    names = list(space.names())
    cat_indices: list[int] = []
    code_to_label: dict[str, dict[int, str]] = {}
    label_to_code: dict[str, dict[str, int]] = {}
    for j, p in enumerate(space.params):
        if isinstance(p, CategoricalParam):
            cat_indices.append(j)
            label_to_code[p.name] = {c: i for i, c in enumerate(p.choices)}
            code_to_label[p.name] = dict(enumerate(p.choices))

    rows: list[list[float]] = []
    ys: list[float] = []
    for t in trials:
        if t.value is None:
            continue
        row: list[float] = []
        for p in space.params:
            val = t.params[p.name]
            if isinstance(p, ContinuousParam | IntParam):
                row.append(float(val))
            else:
                row.append(float(label_to_code[p.name][str(val)]))
        rows.append(row)
        ys.append(float(t.value))
    _ = names
    return (
        np.asarray(rows, dtype=np.float64),
        np.asarray(ys, dtype=np.float64),
        cat_indices,
        code_to_label,
    )


def fit_surrogate(
    space: SearchSpace, trials: Sequence[TrialRecord], seed: int = 0
) -> SurrogateResult:
    completed = [t for t in trials if t.state == "COMPLETE" and t.value is not None]
    names = list(space.names())
    if len(completed) < _MIN_TRIALS:
        return SurrogateResult(feature_importance={}, insights=[], n_trials=len(completed))

    x, y, cat_idx, code_to_label = _encode(space, completed)
    model = lgb.LGBMRegressor(
        n_estimators=200,
        num_leaves=15,
        min_child_samples=5,
        learning_rate=0.05,
        random_state=seed,
        deterministic=True,
        force_row_wise=True,
        verbose=-1,
        n_jobs=1,
    )
    model.fit(x, y, categorical_feature=cat_idx)

    explainer = shap.TreeExplainer(model)
    shap_values = np.asarray(explainer.shap_values(x))  # (n, n_features)

    importance = {names[j]: float(np.mean(np.abs(shap_values[:, j]))) for j in range(len(names))}
    insights = _insights(space, x, shap_values, importance, code_to_label)
    return SurrogateResult(
        feature_importance=importance,
        insights=insights,
        n_trials=len(completed),
        feature_names=names,
    )


def _insights(
    space: SearchSpace,
    x: FloatArray,
    shap_values: FloatArray,
    importance: dict[str, float],
    code_to_label: dict[str, dict[int, str]],
    top_k: int = 3,
) -> list[str]:
    ranked = sorted(importance, key=lambda n: importance[n], reverse=True)
    params_by_name = {p.name: p for p in space.params}
    out: list[str] = []
    for name in ranked[:top_k]:
        j = space.names().index(name)
        imp = importance[name]
        if imp <= 0.0:
            continue
        p = params_by_name[name]
        if isinstance(p, CategoricalParam):
            # The category whose mean SHAP contribution is highest.
            best_code = -1
            best_mean = -np.inf
            for code in code_to_label[name]:
                mask = x[:, j] == code
                if not bool(np.any(mask)):
                    continue
                m = float(np.mean(shap_values[mask, j]))
                if m > best_mean:
                    best_mean, best_code = m, code
            label = code_to_label[name].get(best_code, "?")
            out.append(
                f"{name}={label} is the strongest setting for mean xG "
                f"(SHAP importance {imp:.3f})."
            )
        else:
            corr = float(np.corrcoef(x[:, j], shap_values[:, j])[0, 1]) if x.shape[0] > 1 else 0.0
            direction = "raising" if corr >= 0 else "lowering"
            out.append(f"{direction} {name} tends to increase mean xG (SHAP importance {imp:.3f}).")
    return out

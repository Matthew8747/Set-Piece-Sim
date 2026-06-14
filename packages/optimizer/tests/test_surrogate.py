"""Surrogate + SHAP insights: a LightGBM model over (genome -> mean xG) recovers
the driving feature and emits a plain-language insight (doc 06 sec3.3)."""

import numpy as np

from restart.optimize.genome import CategoricalParam, ContinuousParam, SearchSpace
from restart_opt.study import TrialRecord
from restart_opt.surrogate import fit_surrogate

SPACE = SearchSpace(
    (
        ContinuousParam("target_x", 40.0, 52.0),
        CategoricalParam("delivery_type", ("inswinger", "outswinger")),
    )
)


def _trials(n: int, seed: int) -> list[TrialRecord]:
    rng = np.random.default_rng(seed)
    out: list[TrialRecord] = []
    for _ in range(n):
        tx = float(rng.uniform(40.0, 52.0))
        dt = str(rng.choice(["inswinger", "outswinger"]))
        # delivery_type fully drives the objective; target_x is near-irrelevant.
        y = 0.30 if dt == "inswinger" else 0.05
        out.append(
            TrialRecord(params={"target_x": tx, "delivery_type": dt}, value=y, state="COMPLETE")
        )
    return out


class TestSurrogate:
    def test_recovers_driving_feature(self) -> None:
        res = fit_surrogate(SPACE, _trials(80, 1), seed=1)
        assert res.feature_importance["delivery_type"] >= res.feature_importance["target_x"]

    def test_emits_plain_language_insight(self) -> None:
        res = fit_surrogate(SPACE, _trials(80, 1), seed=1)
        assert len(res.insights) >= 1
        assert any("delivery_type" in s for s in res.insights)

    def test_too_few_trials_returns_empty(self) -> None:
        res = fit_surrogate(SPACE, _trials(3, 1), seed=1)
        assert res.insights == []
        assert res.feature_importance == {}

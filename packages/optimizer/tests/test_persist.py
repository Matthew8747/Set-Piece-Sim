"""Study persistence: a study round-trips to JSON and back without loss."""

import math
from collections.abc import Mapping
from pathlib import Path

from restart.optimize.confirm import ConfirmResult
from restart.optimize.genome import ContinuousParam, SearchSpace
from restart_opt.persist import confirm_to_dict, load_study, outcome_to_dict, save_study
from restart_opt.study import run_study

SPACE = SearchSpace((ContinuousParam("x", 0.0, 10.0),))


def _peak(params: Mapping[str, object]) -> float:
    return math.exp(-((float(params["x"]) - 7.0) ** 2))  # type: ignore[arg-type]


def test_study_round_trips(tmp_path: Path) -> None:
    outcome = run_study(_peak, SPACE, n_trials=8, sampler="tpe", seed=1)
    confirms = [ConfirmResult({"x": 7.0}, 0.21, 0.19, 0.23, 3000, 11)]
    document = {
        "name": "demo",
        "config": {"n_trials": 8, "n_screen": 100},
        "tpe": outcome_to_dict(outcome),
        "confirm": [confirm_to_dict(c) for c in confirms],
    }
    path = save_study("demo", document, root=tmp_path)
    assert path.exists()

    loaded = load_study("demo", root=tmp_path)
    assert loaded["name"] == "demo"
    assert loaded["tpe"]["sampler"] == "tpe"
    assert loaded["tpe"]["best_value"] == outcome.best_value
    assert len(loaded["tpe"]["trials"]) == 8
    assert loaded["confirm"][0]["mean_xg"] == 0.21


def test_generation_index_round_trips(tmp_path: Path) -> None:
    # The NSGA-II lineage (per-trial generation) must survive persistence so the
    # parallel-coordinates view can colour the trial cloud by generation.
    outcome = run_study(_peak, SPACE, n_trials=12, sampler="nsga2", seed=1)
    document = {"name": "evo", "evolution": outcome_to_dict(outcome)}
    save_study("evo", document, root=tmp_path)
    loaded = load_study("evo", root=tmp_path)
    trials = loaded["evolution"]["trials"]
    assert all("generation" in t for t in trials)
    gens = {t["generation"] for t in trials if t["generation"] is not None}
    assert len(gens) >= 2  # generations preserved


def test_save_is_stable_sorted_with_trailing_newline(tmp_path: Path) -> None:
    save_study("s", {"b": 2, "a": 1}, root=tmp_path)
    text = (tmp_path / "s" / "study.json").read_text(encoding="utf-8")
    assert text.endswith("\n")
    # sorted keys -> "a" before "b"
    assert text.index('"a"') < text.index('"b"')

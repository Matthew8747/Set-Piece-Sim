"""Parse persisted ``study.json`` artifacts into the optimization DTOs.

Pure read path: ``json.load`` + typed mapping + small numeric derivations. No
``restart_opt`` import (the optimizer never enters the request path - ADR-008);
no IO beyond reading the committed study files. Derivations (best-so-far,
parallel-coords axes) are module-level functions so they are unit-testable and
the OpenAPI/shared-types drift gate covers the served shapes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from restart import ENGINE_VERSION
from restart_api.schemas import (
    AxisDTO,
    ConfirmRowDTO,
    ConvergencePointDTO,
    MatchupDTO,
    OptimizationDetailDTO,
    OptimizationSummaryDTO,
    SensitivityDTO,
    TrialDTO,
    WinnerDTO,
)

STUDY_FILE = "study.json"


def best_so_far(trials: list[dict[str, Any]]) -> list[ConvergencePointDTO]:
    """Cumulative-max of trial ``value`` over trial order (1-based index).

    Pruned trials may carry no value; they leave the running best unchanged so
    the convergence line is monotone non-decreasing (a running max)."""
    out: list[ConvergencePointDTO] = []
    running: float | None = None
    for i, trial in enumerate(trials, start=1):
        value = trial.get("value")
        if value is not None:
            running = float(value) if running is None else max(running, float(value))
        out.append(
            ConvergencePointDTO(trial=i, best_so_far=running if running is not None else 0.0)
        )
    return out


def axes_from(trials: list[dict[str, Any]], feature_importance: dict[str, float]) -> list[AxisDTO]:
    """One axis per genome parameter, ordered by SHAP importance (desc).

    Numeric params become ``continuous`` with a ``[min, max]`` domain; string
    params become ``categorical`` with a stable (sorted) category order so the
    parallel-coordinates client can ladder them deterministically."""
    # Preserve first-seen key order before re-sorting by importance.
    keys: list[str] = []
    for trial in trials:
        for key in trial.get("params", {}):
            if key not in keys:
                keys.append(key)

    axes: list[AxisDTO] = []
    for name in keys:
        values = [t["params"][name] for t in trials if name in t.get("params", {})]
        importance = float(feature_importance.get(name, 0.0))
        if values and all(isinstance(v, int | float) and not isinstance(v, bool) for v in values):
            nums = [float(v) for v in values]
            axes.append(
                AxisDTO(
                    name=name,
                    kind="continuous",
                    domain=[min(nums), max(nums)],
                    importance=importance,
                )
            )
        else:
            cats = sorted({str(v) for v in values})
            axes.append(
                AxisDTO(name=name, kind="categorical", categories=cats, importance=importance)
            )
    axes.sort(key=lambda a: a.importance, reverse=True)
    return axes


def _stale(study_engine: str) -> bool:
    return study_engine != ENGINE_VERSION


class StudyLoader:
    """Loads committed studies from ``studies_dir`` as read-only data."""

    def __init__(self, studies_dir: Path) -> None:
        self._dir = Path(studies_dir)

    def _read(self, study_id: str) -> dict[str, Any]:
        path = self._dir / study_id / STUDY_FILE
        if not path.is_file():
            raise KeyError(study_id)
        with path.open(encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)
        return data

    def list_summaries(self) -> list[OptimizationSummaryDTO]:
        summaries: list[OptimizationSummaryDTO] = []
        if not self._dir.is_dir():
            return summaries
        for child in sorted(self._dir.iterdir()):
            if not (child / STUDY_FILE).is_file():
                continue
            data = self._read(child.name)
            winner = data["winner"]
            summaries.append(
                OptimizationSummaryDTO(
                    id=child.name,
                    name=data.get("name", child.name),
                    matchup=MatchupDTO(**data["matchup"]),
                    engine_version=data["engine_version"],
                    created_at=data["created_at"],
                    winner_mean_xg=winner["mean_xg"],
                    winner_ci=list(winner["ci"]),
                    beats_baseline=winner["beats_baseline"],
                    n_trials=len(data["tpe"]["trials"]),
                    stale=_stale(data["engine_version"]),
                )
            )
        return summaries

    def get_detail(self, study_id: str) -> OptimizationDetailDTO:
        data = self._read(study_id)
        tpe_trials = data["tpe"]["trials"]
        random_trials = data["random"]["trials"]
        baseline = data["baseline"]
        winner = data["winner"]
        return OptimizationDetailDTO(
            id=study_id,
            name=data.get("name", study_id),
            matchup=MatchupDTO(**data["matchup"]),
            engine_version=data["engine_version"],
            created_at=data["created_at"],
            stale=_stale(data["engine_version"]),
            convergence_tpe=best_so_far(tpe_trials),
            convergence_random=best_so_far(random_trials),
            baseline_mean_xg=baseline["mean_xg"],
            baseline_ci=[baseline["ci_lo"], baseline["ci_hi"]],
            trials=[
                TrialDTO(params=t["params"], value=t["value"], state=t["state"]) for t in tpe_trials
            ],
            axes=axes_from(tpe_trials, data.get("feature_importance", {})),
            confirm=[
                ConfirmRowDTO(
                    params=row["params"],
                    mean_xg=row["mean_xg"],
                    ci_lo=row["ci_lo"],
                    ci_hi=row["ci_hi"],
                    n_sims=row["n_sims"],
                )
                for row in data["confirm"]
            ],
            feature_importance=data.get("feature_importance", {}),
            insights=data.get("insights", []),
            sensitivity=SensitivityDTO(
                verdict=data["sensitivity"]["verdict"],
                top1_stable=data["sensitivity"]["top1_stable"],
                rankings_flip=data["sensitivity"]["rankings_flip"],
                flipped=data["sensitivity"]["flipped"],
            ),
            winner=WinnerDTO(
                mean_xg=winner["mean_xg"],
                ci=list(winner["ci"]),
                beats_baseline=winner["beats_baseline"],
                boundary_flags=winner["boundary_flags"],
                face_validity_flags=winner["face_validity_flags"],
            ),
        )

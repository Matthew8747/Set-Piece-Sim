"""Optuna study drivers: TPE (recommended primary) and the mandatory
random-search baseline at equal budget (design doc 06 sec3.2).

Both samplers are seeded, so a study is reproducible (seed in => same trials
out). Infeasible genomes (the objective raises ``ValueError``) are reported to
Optuna as pruned trials, not crashes — the optimizer learns the real
constraints (doc 06 sec3.1). The objective is *maximized* (mean xG, higher is
better).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import optuna

from restart.optimize.genome import (
    CategoricalParam,
    ContinuousParam,
    IntParam,
    ParamValue,
    SearchSpace,
)
from restart.optimize.objective import ObjectiveFunction

# Optuna's per-trial INFO logging is noise in CI/test output.
optuna.logging.set_verbosity(optuna.logging.WARNING)

Sampler = str  # "tpe" | "random"


@dataclass(frozen=True, slots=True)
class TrialRecord:
    params: dict[str, ParamValue]
    value: float | None
    state: str  # COMPLETE | PRUNED | FAIL


@dataclass(frozen=True, slots=True)
class StudyOutcome:
    sampler: Sampler
    n_trials: int
    seed: int
    best_params: dict[str, ParamValue]
    best_value: float
    trials: list[TrialRecord]

    def completed(self) -> list[TrialRecord]:
        return [t for t in self.trials if t.state == "COMPLETE" and t.value is not None]


def suggest(trial: optuna.Trial, space: SearchSpace) -> dict[str, ParamValue]:
    """Map a pure SearchSpace to Optuna suggestions, dispatched per param type."""
    out: dict[str, ParamValue] = {}
    for p in space.params:
        if isinstance(p, ContinuousParam):
            out[p.name] = trial.suggest_float(p.name, p.lo, p.hi)
        elif isinstance(p, IntParam):
            out[p.name] = trial.suggest_int(p.name, p.lo, p.hi)
        elif isinstance(p, CategoricalParam):
            out[p.name] = trial.suggest_categorical(p.name, list(p.choices))
        else:  # pragma: no cover - defensive; Param is a closed set today
            raise TypeError(f"unsupported param type for {p.name}: {type(p)}")
    return out


def make_sampler(sampler: Sampler, seed: int) -> optuna.samplers.BaseSampler:
    if sampler == "tpe":
        return optuna.samplers.TPESampler(seed=seed)
    if sampler == "random":
        return optuna.samplers.RandomSampler(seed=seed)
    raise ValueError(f"unknown sampler {sampler!r} (expected 'tpe' or 'random')")


def run_study(
    objective: ObjectiveFunction,
    space: SearchSpace,
    n_trials: int,
    sampler: Sampler = "tpe",
    seed: int = 0,
) -> StudyOutcome:
    """Run one study (no pruning): every trial spends the full per-trial budget.

    This is the fair equal-budget setting for the TPE-vs-random comparison and
    the engine-free toy-landscape test. The engine-backed, pruning screen lives
    in :func:`restart_opt.screen.run_screen`.
    """
    study = optuna.create_study(direction="maximize", sampler=make_sampler(sampler, seed))

    def _objective(trial: optuna.Trial) -> float:
        params = suggest(trial, space)
        try:
            return float(objective(params))
        except ValueError as exc:  # infeasible genome -> prune, don't crash
            raise optuna.TrialPruned() from exc

    study.optimize(_objective, n_trials=n_trials, show_progress_bar=False)
    return build_outcome(study, sampler, n_trials, seed)


def build_outcome(study: optuna.Study, sampler: Sampler, n_trials: int, seed: int) -> StudyOutcome:
    records = [
        TrialRecord(
            params=dict(t.params),
            value=(None if t.value is None else float(t.value)),
            state=t.state.name,
        )
        for t in study.trials
    ]
    best: dict[str, Any] = dict(study.best_params)
    return StudyOutcome(
        sampler=sampler,
        n_trials=n_trials,
        seed=seed,
        best_params=best,
        best_value=float(study.best_value),
        trials=records,
    )

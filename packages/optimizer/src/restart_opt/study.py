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

Sampler = str  # "tpe" | "random" | "cmaes" | "nsga2"


#: Evolutionary samplers run a *population* per generation, so the population
#: must be sized to the trial budget or fewer than one generation occurs (no
#: actual evolution). This default yields ~3 generations at the canonical budget.
def default_population(n_trials: int) -> int:
    return max(4, n_trials // 3)


@dataclass(frozen=True, slots=True)
class TrialRecord:
    params: dict[str, ParamValue]
    value: float | None
    state: str  # COMPLETE | PRUNED | FAIL
    #: Generation index for population-based samplers (NSGA-II); None otherwise.
    generation: int | None = None


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


def make_sampler(
    sampler: Sampler, seed: int, population_size: int | None = None
) -> optuna.samplers.BaseSampler:
    """Map a sampler name to a seeded Optuna sampler.

    ``cmaes`` (an evolution strategy, strongest on the continuous genes) and
    ``nsga2`` (a genetic algorithm that evolves the *full* mixed genome via
    selection/crossover/mutation) are the evolutionary search options — both plug
    into the same screen→confirm pipeline as TPE/random (Phase 9, ADR-010)."""
    if sampler == "tpe":
        return optuna.samplers.TPESampler(seed=seed)
    if sampler == "random":
        return optuna.samplers.RandomSampler(seed=seed)
    if sampler == "cmaes":
        return optuna.samplers.CmaEsSampler(seed=seed)
    if sampler == "nsga2":
        return optuna.samplers.NSGAIISampler(seed=seed, population_size=population_size or 8)
    raise ValueError(
        f"unknown sampler {sampler!r} (expected one of 'tpe', 'random', 'cmaes', 'nsga2')"
    )


def is_evolutionary(sampler: Sampler) -> bool:
    """Evolutionary samplers need full evaluations to update their population, so
    the screen runs them with pruning OFF (mid-trial pruning corrupts a generation)."""
    return sampler in ("cmaes", "nsga2")


def run_study(
    objective: ObjectiveFunction,
    space: SearchSpace,
    n_trials: int,
    sampler: Sampler = "tpe",
    seed: int = 0,
    population_size: int | None = None,
) -> StudyOutcome:
    """Run one study (no pruning): every trial spends the full per-trial budget.

    This is the fair equal-budget setting for the sampler comparison and the
    engine-free toy-landscape test. The engine-backed, pruning screen lives in
    :func:`restart_opt.screen.run_screen`. For evolutionary samplers the
    population is sized to the budget so real generations occur.
    """
    pop = population_size if population_size is not None else default_population(n_trials)
    study = optuna.create_study(
        direction="maximize", sampler=make_sampler(sampler, seed, population_size=pop)
    )

    def _objective(trial: optuna.Trial) -> float:
        params = suggest(trial, space)
        try:
            return float(objective(params))
        except ValueError as exc:  # infeasible genome -> prune, don't crash
            raise optuna.TrialPruned() from exc

    study.optimize(_objective, n_trials=n_trials, show_progress_bar=False)
    return build_outcome(study, sampler, n_trials, seed)


#: Optuna has used both keys across versions for the NSGA-II generation index.
_GENERATION_KEYS = ("NSGAIISampler:generation", "nsga2:generation")


def _generation_of(trial: optuna.trial.FrozenTrial) -> int | None:
    """NSGA-II records its generation in system_attrs; other samplers don't."""
    for key in _GENERATION_KEYS:
        gen = trial.system_attrs.get(key)
        if gen is not None:
            return int(gen)
    return None


def build_outcome(study: optuna.Study, sampler: Sampler, n_trials: int, seed: int) -> StudyOutcome:
    records = [
        TrialRecord(
            params=dict(t.params),
            value=(None if t.value is None else float(t.value)),
            state=t.state.name,
            generation=_generation_of(t),
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

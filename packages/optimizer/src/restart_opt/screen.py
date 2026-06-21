"""Engine-backed screen + confirm (the screen-then-confirm pipeline, doc 06
sec3.2).

The screen evaluates each genome at a small budget under common random numbers
(every trial sees the same per-sim seeds), reporting running mean xG in chunks so
Optuna's MedianPruner can abandon clearly-poor genomes early. The confirm stage
re-evaluates the screen's top-k at a large budget, again under CRN, and compares
them to the library baseline by non-overlapping 95% CIs.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import numpy as np
import optuna

from restart.engine import SetPieceEngine
from restart.engine.xg import XGModelBundle
from restart.montecarlo.runner import MonteCarloRunner, sim_seeds
from restart.optimize.confirm import ConfirmResult, confirm_candidates, mean_ci, mean_xg_samples
from restart.optimize.genome import Genome
from restart.simulation.events import ShotEvent
from restart.tactics.compile import Scenario, compile_scenario
from restart_opt.study import (
    Sampler,
    StudyOutcome,
    build_outcome,
    default_population,
    is_evolutionary,
    make_sampler,
    suggest,
)


def _xg_of(result: object) -> float:
    events = getattr(result, "events", ())
    shot = next((e for e in events if isinstance(e, ShotEvent)), None)
    return float(shot.xg) if shot is not None and shot.xg is not None else 0.0


def run_screen(
    base: Scenario,
    genome: Genome,
    bundle: XGModelBundle,
    n_trials: int,
    n_screen: int,
    sampler: Sampler = "tpe",
    seed: int = 0,
    n_chunks: int = 4,
    prune: bool = True,
    population_size: int | None = None,
) -> StudyOutcome:
    """Optuna screen at ``n_screen`` sims/trial with CRN + optional median pruning.

    Evolutionary samplers (``cmaes``/``nsga2``) need full evaluations to update
    their population, so pruning is forced off for them regardless of ``prune``
    (a mid-trial prune would corrupt a generation). The population is sized to the
    trial budget so real generations occur.
    """
    engine = SetPieceEngine(xg_scorer=bundle)
    space = genome.space
    seeds = sim_seeds(seed, n_screen)  # CRN: identical seed stream for every trial
    chunks = [list(c) for c in np.array_split(np.array(seeds), min(n_chunks, n_screen))]
    use_pruner = prune and not is_evolutionary(sampler)
    pruner: optuna.pruners.BasePruner = (
        optuna.pruners.MedianPruner(n_warmup_steps=1) if use_pruner else optuna.pruners.NopPruner()
    )
    pop = population_size if population_size is not None else default_population(n_trials)
    study = optuna.create_study(
        direction="maximize",
        sampler=make_sampler(sampler, seed, population_size=pop),
        pruner=pruner,
    )

    def objective(trial: optuna.Trial) -> float:
        params = suggest(trial, space)
        try:
            scenario = genome.to_scenario(base, params)
        except ValueError as exc:
            raise optuna.TrialPruned() from exc
        program = compile_scenario(scenario)
        xg: list[float] = []
        for step, chunk in enumerate(chunks):
            for s in chunk:
                xg.append(_xg_of(engine.run(program, int(s))))
            trial.report(float(np.mean(xg)), step)
            if trial.should_prune():
                raise optuna.TrialPruned()
        return float(np.mean(xg))

    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return build_outcome(study, sampler, n_trials, seed)


def samples_fn(
    base: Scenario, genome: Genome, runner: MonteCarloRunner
) -> Callable[[Mapping[str, object], int, int], np.ndarray]:
    """A per-sim-xG sampler for the confirm stage, bound to one runner/genome."""

    def make_samples(params: Mapping[str, object], n: int, root_seed: int) -> np.ndarray:
        program = compile_scenario(genome.to_scenario(base, params))
        return mean_xg_samples(runner.run(program, n, root_seed))

    return make_samples


def top_k_params(outcome: StudyOutcome, k: int) -> list[dict[str, object]]:
    """The k highest-scoring completed trials' params (dedup-stable, best first)."""
    completed = sorted(
        outcome.completed(), key=lambda t: (t.value if t.value is not None else -1.0), reverse=True
    )
    seen: list[dict[str, object]] = []
    for t in completed:
        params: dict[str, object] = dict(t.params)
        if params not in seen:
            seen.append(params)
        if len(seen) >= k:
            break
    return seen


def confirm_params(
    base: Scenario,
    genome: Genome,
    bundle: XGModelBundle,
    candidates: Sequence[Mapping[str, object]],
    n_confirm: int,
    root_seed: int,
) -> list[ConfirmResult]:
    """Confirm an explicit list of candidate genomes under one CRN seed (so the
    candidates — whatever sampler found them — are compared on equal footing)."""
    runner = MonteCarloRunner(engine=SetPieceEngine(xg_scorer=bundle))
    return confirm_candidates(samples_fn(base, genome, runner), candidates, n_confirm, root_seed)


def confirm_top_k(
    base: Scenario,
    genome: Genome,
    bundle: XGModelBundle,
    outcome: StudyOutcome,
    k: int,
    n_confirm: int,
    root_seed: int,
) -> list[ConfirmResult]:
    return confirm_params(base, genome, bundle, top_k_params(outcome, k), n_confirm, root_seed)


def confirm_scenario(
    scenario: Scenario, bundle: XGModelBundle, n_confirm: int, root_seed: int
) -> ConfirmResult:
    """Confirm a fixed Scenario (e.g. the library baseline) under the same CRN seed."""
    runner = MonteCarloRunner(engine=SetPieceEngine(xg_scorer=bundle))
    program = compile_scenario(scenario)
    samples = mean_xg_samples(runner.run(program, n_confirm, root_seed))
    mean, lo, hi = mean_ci(samples)
    return ConfirmResult(
        params={"baseline": scenario.routine.name},
        mean_xg=mean,
        ci_lo=lo,
        ci_hi=hi,
        n_sims=n_confirm,
        root_seed=root_seed,
    )

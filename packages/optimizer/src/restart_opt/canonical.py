"""The canonical study: England corners vs Argentina zonal (roadmap Phase 5).

Wires the whole pipeline together: TPE screen + equal-budget random baseline ->
confirm the top-k at a large budget under CRN -> compare the winner to the
library baseline by non-overlapping CIs -> anti-exploit + face-validity check ->
SHAP insights -> attribute sensitivity -> persist + log. Squads are the demo
squads (squad selection from marts is Phase 6); this is documented in the writeup.

Throughput reality (~3 sims/s reference engine, ADR-003 d8 kernel deferred): the
default budget is the reduced, honest budget the reference engine can finish
offline. The full reference budget (500 screen / 10k confirm) is the documented
methodology; pass larger budgets to reproduce it once the kernel lands.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from restart import ENGINE_VERSION
from restart.engine.xg import XGModelBundle
from restart.montecarlo.runner import MonteCarloRunner
from restart.optimize.boundary import boundary_flags, face_validity_flags
from restart.optimize.confirm import beats_baseline
from restart.optimize.genome import CornerGenome, Genome
from restart.optimize.objective import RoutineObjective
from restart.players.player import PositionGroup
from restart.players.team import Team
from restart.tactics.compile import Scenario
from restart.tactics.library import near_post_inswinger, zonal_six_two
from restart.tactics.routine import RoutineSpec
from restart_opt import OPT_VERSION
from restart_opt.bundle import load_bundle, xg_engine
from restart_opt.persist import confirm_to_dict, outcome_to_dict, save_study
from restart_opt.screen import confirm_scenario, confirm_top_k, run_screen, top_k_params
from restart_opt.sensitivity import perturb_team, rank_stability
from restart_opt.surrogate import fit_surrogate

_CANONICAL_NAME = "england-vs-argentina"


@dataclass(frozen=True, slots=True)
class CanonicalConfig:
    n_trials: int = 40
    n_screen: int = 250
    k: int = 3
    n_confirm: int = 3000
    sensitivity_sims: int = 200
    seed: int = 0
    prune: bool = True


def _scenario_for(routine: RoutineSpec, att: Team, deff: Team) -> Scenario:
    kicker = max(att.players, key=lambda p: p.attributes.delivery).player_id
    outfield = [
        p.player_id
        for p in att.players
        if p.position_group is not PositionGroup.GK and p.player_id != kicker
    ]
    roles = {a.role: outfield[i] for i, a in enumerate(routine.assignments)}
    return Scenario(
        routine=routine,
        attacking_team=att,
        defending_team=deff,
        kicker_id=kicker,
        role_assignments=roles,
        scheme=zonal_six_two(),
    )


def _eval_mean_xg(
    att: Team,
    deff: Team,
    genome: Genome,
    bundle: XGModelBundle,
    params: Mapping[str, object],
    n_sims: int,
    seed: int,
) -> float:
    base = _scenario_for(near_post_inswinger(), att, deff)
    runner = MonteCarloRunner(engine=xg_engine(bundle))
    return RoutineObjective(base, genome, runner=runner, n_sims=n_sims, root_seed=seed)(params)


def _sensitivity(
    att: Team,
    deff: Team,
    genome: Genome,
    bundle: XGModelBundle,
    candidates: Sequence[Mapping[str, object]],
    n_sims: int,
    seed: int,
) -> dict[str, Any]:
    ids = [f"cand_{i}" for i in range(len(candidates))]
    base_scores = {
        ids[i]: _eval_mean_xg(att, deff, genome, bundle, candidates[i], n_sims, seed)
        for i in range(len(candidates))
    }
    perturbed: dict[str, dict[str, float]] = {}
    for label, frac in (("+10%", 0.10), ("-10%", -0.10)):
        att_p = perturb_team(att, frac)
        perturbed[label] = {
            ids[i]: _eval_mean_xg(att_p, deff, genome, bundle, candidates[i], n_sims, seed)
            for i in range(len(candidates))
        }
    res = rank_stability(base_scores, perturbed)
    return {
        "verdict": res.verdict,
        "top1_stable": res.top1_stable,
        "rankings_flip": res.rankings_flip,
        "flipped": res.flipped,
        "baseline_order": res.baseline_order,
        "frac": 0.10,
    }


def run_canonical(
    config: CanonicalConfig | None = None,
    *,
    att: Team | None = None,
    deff: Team | None = None,
    bundle: XGModelBundle | None = None,
    out_root: Path | None = None,
) -> dict[str, Any]:
    """Run the canonical study and return its persisted document."""
    from restart.players.demo import demo_team  # local: demo squads are a P6 stand-in

    cfg = config if config is not None else CanonicalConfig()
    att = att if att is not None else demo_team("ENG", "England", 1)
    deff = deff if deff is not None else demo_team("ARG", "Argentina", 2)
    bundle = bundle if bundle is not None else load_bundle()
    genome = CornerGenome()
    base = _scenario_for(near_post_inswinger(), att, deff)
    confirm_seed = cfg.seed + 1000

    tpe = run_screen(
        base, genome, bundle, cfg.n_trials, cfg.n_screen, "tpe", cfg.seed, prune=cfg.prune
    )
    rnd = run_screen(
        base, genome, bundle, cfg.n_trials, cfg.n_screen, "random", cfg.seed, prune=False
    )

    confirms = confirm_top_k(base, genome, bundle, tpe, cfg.k, cfg.n_confirm, confirm_seed)
    baseline_cr = confirm_scenario(base, bundle, cfg.n_confirm, confirm_seed)
    winner = max(confirms, key=lambda c: c.mean_xg) if confirms else baseline_cr
    beats = beats_baseline(winner.ci, baseline_cr.ci)

    bflags = boundary_flags(genome.space, winner.params)
    fflags = face_validity_flags(winner.mean_xg, bflags)

    surrogate = fit_surrogate(genome.space, tpe.trials, seed=cfg.seed)
    sensitivity = _sensitivity(
        att, deff, genome, bundle, top_k_params(tpe, cfg.k), cfg.sensitivity_sims, cfg.seed
    )

    document: dict[str, Any] = {
        "name": _CANONICAL_NAME,
        "created_at": datetime.now(UTC).isoformat(),
        "engine_version": ENGINE_VERSION,
        "opt_version": OPT_VERSION,
        "matchup": {"attacking": att.name, "defending": deff.name, "scheme": "zonal_six_two"},
        "config": {
            "n_trials": cfg.n_trials,
            "n_screen": cfg.n_screen,
            "k": cfg.k,
            "n_confirm": cfg.n_confirm,
            "seed": cfg.seed,
            "prune": cfg.prune,
        },
        "tpe": outcome_to_dict(tpe),
        "random": outcome_to_dict(rnd),
        "confirm": [confirm_to_dict(c) for c in confirms],
        "baseline": confirm_to_dict(baseline_cr),
        "winner": {
            "params": winner.params,
            "mean_xg": winner.mean_xg,
            "ci": list(winner.ci),
            "beats_baseline": beats,
            "boundary_flags": bflags,
            "face_validity_flags": fflags,
        },
        "insights": surrogate.insights,
        "feature_importance": surrogate.feature_importance,
        "sensitivity": sensitivity,
    }
    save_study(_CANONICAL_NAME, document, root=out_root)
    return document

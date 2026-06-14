"""Engine-backed screen: a small study with the committed xG bundle is
reproducible (same seed => same best), and the confirm stage is CRN-deterministic.

Tiny budgets keep this fast on the ~3 sims/s reference engine."""

from collections.abc import Mapping

from restart.optimize.genome import CornerGenome
from restart.players.demo import demo_team
from restart.players.player import PositionGroup
from restart.tactics.compile import Scenario
from restart.tactics.library import all_corner_routines, all_schemes
from restart_opt.bundle import load_bundle, xg_runner
from restart_opt.screen import run_screen, samples_fn

ATT = demo_team("ENG", "England", 1)
DEF = demo_team("ARG", "Argentina", 2)


def base_scenario() -> Scenario:
    routine = all_corner_routines()[0]
    kicker = max(ATT.players, key=lambda p: p.attributes.delivery).player_id
    outfield = [
        p.player_id
        for p in ATT.players
        if p.position_group is not PositionGroup.GK and p.player_id != kicker
    ]
    roles = {a.role: outfield[i] for i, a in enumerate(routine.assignments)}
    return Scenario(
        routine=routine,
        attacking_team=ATT,
        defending_team=DEF,
        kicker_id=kicker,
        role_assignments=roles,
        scheme=all_schemes()[0],
    )


def test_screen_reproducible_same_seed() -> None:
    bundle = load_bundle()
    genome = CornerGenome()
    base = base_scenario()
    a = run_screen(base, genome, bundle, n_trials=4, n_screen=6, sampler="tpe", seed=1, n_chunks=2)
    b = run_screen(base, genome, bundle, n_trials=4, n_screen=6, sampler="tpe", seed=1, n_chunks=2)
    assert a.best_params == b.best_params
    assert a.best_value == b.best_value


def test_confirm_samples_crn_deterministic() -> None:
    genome = CornerGenome()
    base = base_scenario()
    make = samples_fn(base, genome, xg_runner())
    v: Mapping[str, object] = genome.defaults()
    s1 = make(v, 8, 5)
    s2 = make(v, 8, 5)
    assert list(s1) == list(s2)

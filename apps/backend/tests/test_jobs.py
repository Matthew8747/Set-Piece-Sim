"""Batch runner: determinism, progress, bounded xG samples (ADR-007 d3)."""

from restart.montecarlo import MonteCarloRunner, build_report
from restart.players.demo import demo_team
from restart.players.player import PositionGroup
from restart.tactics.compile import Scenario, SimProgram, compile_scenario
from restart.tactics.library import all_corner_routines, all_schemes
from restart_api.jobs.runner import MAX_XG_SAMPLES, per_sim_xg, run_batch, subsample


def _program() -> SimProgram:
    att = demo_team("A", "Alpha", 1)
    deff = demo_team("B", "Beta", 2)
    routine = all_corner_routines()[0]
    scheme = all_schemes()[0]
    kicker = max(att.players, key=lambda p: p.attributes.delivery).player_id
    outfield = [
        p.player_id
        for p in att.players
        if p.position_group is not PositionGroup.GK and p.player_id != kicker
    ]
    roles = {a.role: outfield[i] for i, a in enumerate(routine.assignments)}
    return compile_scenario(
        Scenario(
            routine=routine,
            attacking_team=att,
            defending_team=deff,
            kicker_id=kicker,
            role_assignments=roles,
            scheme=scheme,
        )
    )


def test_run_batch_matches_build_report() -> None:
    runner = MonteCarloRunner()
    program = _program()
    report, _ = run_batch(runner, program, n_sims=40, root_seed=7)
    expected = build_report(runner.run(program, 40, 7)).to_dict()
    assert report == expected


def test_progress_is_monotonic_and_completes() -> None:
    seen: list[tuple[int, int]] = []
    run_batch(
        MonteCarloRunner(),
        _program(),
        n_sims=100,
        root_seed=1,
        progress=lambda d, t: seen.append((d, t)),
    )
    assert seen, "no progress reported"
    dones = [d for d, _ in seen]
    assert dones == sorted(dones)
    assert seen[-1] == (100, 100)


def test_xg_samples_bounded() -> None:
    _, samples = run_batch(MonteCarloRunner(), _program(), n_sims=40, root_seed=2)
    assert len(samples) <= MAX_XG_SAMPLES
    assert len(samples) == 40  # n_sims <= cap -> all kept


def test_per_sim_xg_length_matches_batch() -> None:
    batch = MonteCarloRunner().run(_program(), 30, 3)
    assert len(per_sim_xg(batch)) == 30


def test_subsample_is_bounded_and_deterministic() -> None:
    values = [float(i) for i in range(1000)]
    a = subsample(values, 50, seed=11)
    b = subsample(values, 50, seed=11)
    assert a == b
    assert len(a) == 50
    # Small inputs are returned whole, in order.
    assert subsample([1.0, 2.0, 3.0], 50, seed=11) == [1.0, 2.0, 3.0]

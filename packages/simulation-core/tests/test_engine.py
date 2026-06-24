"""Set-piece engine tests: terminal outcomes, invariants, determinism,
free-kick feasibility (PRD A-3), and event-stream integrity."""

from collections import Counter

import numpy as np
import pytest

from restart.engine import SetPieceEngine, SetPieceResult
from restart.players.attributes import Attr
from restart.players.demo import demo_team
from restart.players.player import PositionGroup
from restart.players.team import Team
from restart.simulation.events import FirstContactEvent, SetPieceOutcome, ShotEvent
from restart.tactics.compile import Scenario, SimProgram, compile_scenario
from restart.tactics.library import all_corner_routines, all_schemes, direct_free_kick
from restart.tactics.routine import PitchPoint, RoutineSpec
from restart.tactics.scheme import DefensiveScheme

ATT = demo_team("ENG", "England", 1)
DEF = demo_team("ARG", "Argentina", 2)


def build_program(
    routine: RoutineSpec,
    scheme: DefensiveScheme,
    attacking: Team = ATT,
    defending: Team = DEF,
    fk_position: PitchPoint | None = None,
) -> SimProgram:
    kicker = max(attacking.players, key=lambda p: p.attributes.delivery).player_id
    outfield = [
        p.player_id
        for p in attacking.players
        if p.position_group is not PositionGroup.GK and p.player_id != kicker
    ]
    roles = {a.role: outfield[i] for i, a in enumerate(routine.assignments)}
    scenario = Scenario(
        routine=routine,
        attacking_team=attacking,
        defending_team=defending,
        kicker_id=kicker,
        role_assignments=roles,
        scheme=scheme,
        fk_position=fk_position,
    )
    return compile_scenario(scenario)


ENGINE = SetPieceEngine()


class TestCornersRunToTerminal:
    @pytest.mark.parametrize("routine_idx", range(5))
    @pytest.mark.parametrize("scheme_idx", range(2))
    def test_corner_terminates_with_valid_outcome(self, routine_idx: int, scheme_idx: int) -> None:
        """Roadmap Phase-2 acceptance: scripted corners run start-to-terminal."""
        program = build_program(all_corner_routines()[routine_idx], all_schemes()[scheme_idx])
        result = ENGINE.run(program, seed=routine_idx * 10 + scheme_idx)
        assert isinstance(result.outcome, SetPieceOutcome)
        assert result.events[0].kind == "launch"
        times = [e.time_s for e in result.events]
        assert times == sorted(times)

    def test_kinematic_envelope_never_violated(self) -> None:
        """No agent exceeds top speed (G-1) - checked from recorded tracks."""
        program = build_program(all_corner_routines()[0], all_schemes()[0])
        result = ENGINE.run(program, seed=3)
        dt = np.diff(result.track_times_s)
        for tracks, attr in (
            (result.att_tracks, program.att_attr),
            (result.def_tracks, program.def_attr),
        ):
            step = np.linalg.norm(np.diff(tracks, axis=0), axis=2)  # (T-1, n)
            speeds = step / dt[:, np.newaxis]
            # Separation nudges can add a hair above top speed; tolerance 5%.
            assert np.all(speeds <= attr[:, Attr.TOP_SPEED] * 1.05 + 1e-9)


class TestDeterminism:
    def test_same_seed_identical(self) -> None:
        program = build_program(all_corner_routines()[0], all_schemes()[0])
        a = ENGINE.run(program, seed=42)
        b = ENGINE.run(program, seed=42)
        assert a.outcome == b.outcome
        assert [e.kind for e in a.events] == [e.kind for e in b.events]
        np.testing.assert_array_equal(a.att_tracks, b.att_tracks)
        np.testing.assert_array_equal(a.def_tracks, b.def_tracks)

    def test_different_seeds_vary(self) -> None:
        program = build_program(all_corner_routines()[0], all_schemes()[0])
        outcomes = {ENGINE.run(program, seed=s).outcome for s in range(25)}
        assert len(outcomes) >= 2  # stochastic elements actually bite


class TestOutcomePlausibility:
    def test_distribution_loose_sanity(self) -> None:
        """NOT calibration (Phase 3) - only 'the sim is not degenerate'."""
        counts: Counter[SetPieceOutcome] = Counter()
        n = 0
        for r_idx in range(3):
            program = build_program(all_corner_routines()[r_idx], all_schemes()[0])
            for seed in range(30):
                counts[ENGINE.run(program, seed).outcome] += 1
                n += 1
        goal_rate = counts[SetPieceOutcome.GOAL] / n
        assert goal_rate < 0.30  # not a goal machine
        contested = sum(
            counts[o]
            for o in (
                SetPieceOutcome.GOAL,
                SetPieceOutcome.SAVED,
                SetPieceOutcome.OFF_TARGET,
                SetPieceOutcome.CLEARED,
                SetPieceOutcome.KEEPER_CLAIM,
            )
        )
        assert contested / n > 0.5  # most deliveries get contested

    def test_shot_event_features_sane(self) -> None:
        program = build_program(all_corner_routines()[0], all_schemes()[0])
        shots = [
            e
            for seed in range(40)
            for e in ENGINE.run(program, seed).events
            if isinstance(e, ShotEvent)
        ]
        assert shots, "40 corners must produce at least one shot"
        for s in shots:
            assert 0.0 < s.distance_m < 40.0
            assert 0.0 < s.angle_rad < np.pi
            assert 0.0 < s.speed_ms <= 32.0  # P-12 cap

    def test_first_contact_event_precedes_resolution(self) -> None:
        program = build_program(all_corner_routines()[0], all_schemes()[0])
        for seed in range(20):
            result = ENGINE.run(program, seed)
            kinds = [e.kind for e in result.events]
            if result.outcome in (
                SetPieceOutcome.GOAL,
                SetPieceOutcome.SAVED,
                SetPieceOutcome.OFF_TARGET,
                SetPieceOutcome.CLEARED,
                SetPieceOutcome.KEEPER_CLAIM,
            ):
                assert "firstcontact" in kinds
                fc = next(e for e in result.events if isinstance(e, FirstContactEvent))
                assert fc.player_id  # labeled for replay/analytics


class TestFreeKickFeasibility:
    """PRD assumption A-3: free kicks are configuration, not construction."""

    def test_direct_free_kick_compiles_and_runs(self) -> None:
        scheme = DefensiveScheme(
            name="fk-wall",
            zonal_points=tuple(
                PitchPoint(x=x, y=y)
                for x, y in [(48.0, -3.0), (48.0, 0.0), (48.0, 3.0), (44.0, -6.0), (44.0, 6.0)]
            ),
            n_man_markers=1,
            wall_size=4,
        )
        program = build_program(direct_free_kick(), scheme, fk_position=PitchPoint(x=30.0, y=4.0))
        assert program.set_piece == 1
        result = ENGINE.run(program, seed=11)
        assert isinstance(result, SetPieceResult)
        assert isinstance(result.outcome, SetPieceOutcome)


class TestReplayPayload:
    def test_tracks_read_only_and_shaped(self) -> None:
        program = build_program(all_corner_routines()[1], all_schemes()[1])
        result = ENGINE.run(program, seed=5)
        t = len(result.track_times_s)
        assert result.att_tracks.shape == (t, program.n_attackers, 2)
        assert result.def_tracks.shape == (t, program.n_defenders, 2)
        with pytest.raises(ValueError, match="read-only"):
            result.att_tracks[0, 0, 0] = 0.0

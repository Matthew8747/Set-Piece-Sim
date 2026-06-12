"""Tests for compile_scenario() → SimProgram (ADR-004 d4).

Verifies shapes, dtypes, read-only enforcement, marking assignment logic,
wall placement, zonal fill, determinism, and full library cross-compilation.
"""

from __future__ import annotations

import numpy as np
import pytest

from restart.players.attributes import N_ATTR
from restart.players.demo import demo_team
from restart.tactics.compile import Scenario, SimProgram, compile_scenario
from restart.tactics.library import (
    all_corner_routines,
    all_schemes,
    direct_free_kick,
    hybrid,
    man_marking_heavy,
    zonal_six_two,
)
from restart.tactics.routine import (
    PitchPoint,
    RoutineSpec,
)
from restart.tactics.scheme import DefensiveScheme

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SEED_ATT = 42
_SEED_DEF = 7


def _att_team() -> object:
    return demo_team("ATT", "Attackers FC", seed=_SEED_ATT)


def _def_team() -> object:
    return demo_team("DEF", "Defenders FC", seed=_SEED_DEF)


def _corner_scenario(
    routine: RoutineSpec | None = None,
    scheme: DefensiveScheme | None = None,
    corner_side: str = "right",
) -> Scenario:
    from restart.players.demo import demo_team as _dt

    att = _dt("ATT", "Attackers FC", seed=_SEED_ATT)
    dff = _dt("DEF", "Defenders FC", seed=_SEED_DEF)

    if routine is None:
        from restart.tactics.library import near_post_inswinger

        routine = near_post_inswinger()
    if scheme is None:
        scheme = zonal_six_two()

    # Build role_assignments: map each role to the first available attacker
    # who isn't the kicker. Use kicker = first player with delivery >= 0.8.
    kicker = next(p for p in att.players if p.attributes.delivery >= 0.8)
    non_kickers = [p for p in att.players if p.player_id != kicker.player_id]
    role_assignments = {
        assignment.role: non_kickers[i].player_id
        for i, assignment in enumerate(routine.assignments)
    }

    return Scenario(
        routine=routine,
        attacking_team=att,
        defending_team=dff,
        kicker_id=kicker.player_id,
        role_assignments=role_assignments,
        scheme=scheme,
        corner_side=corner_side,
    )


def _fk_scenario(
    wall_size: int = 3,
    fk_x: float = 30.0,
    fk_y: float = 5.0,
) -> Scenario:
    from restart.players.demo import demo_team as _dt

    att = _dt("ATT", "Attackers FC", seed=_SEED_ATT)
    dff = _dt("DEF", "Defenders FC", seed=_SEED_DEF)
    routine = direct_free_kick()

    # FK scheme: must have wall_size + zonal + markers = 10
    n_zonal = 10 - wall_size - 2
    zonal_pts = tuple(PitchPoint(x=44.0, y=float(i) - float(n_zonal) / 2) for i in range(n_zonal))
    scheme = DefensiveScheme(
        name=f"fk_wall_{wall_size}",
        zonal_points=zonal_pts,
        n_man_markers=2,
        wall_size=wall_size,
    )

    kicker = next(p for p in att.players if p.attributes.delivery >= 0.8)
    non_kickers = [p for p in att.players if p.player_id != kicker.player_id]
    role_assignments = {
        assignment.role: non_kickers[i].player_id
        for i, assignment in enumerate(routine.assignments)
    }

    return Scenario(
        routine=routine,
        attacking_team=att,
        defending_team=dff,
        kicker_id=kicker.player_id,
        role_assignments=role_assignments,
        scheme=scheme,
        fk_position=PitchPoint(x=fk_x, y=fk_y),
    )


# ---------------------------------------------------------------------------
# Shape and dtype tests
# ---------------------------------------------------------------------------


class TestSimProgramShapes:
    def test_is_simprogram(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        assert isinstance(prog, SimProgram)

    def test_att_attr_shape(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        na = prog.n_attackers
        assert prog.att_attr.shape == (na, N_ATTR)
        assert prog.att_attr.dtype == np.float64

    def test_att_start_shape(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        na = prog.n_attackers
        assert prog.att_start.shape == (na, 2)
        assert prog.att_start.dtype == np.float64

    def test_att_intent_shape_dtype(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        na = prog.n_attackers
        assert prog.att_intent.shape == (na,)
        assert prog.att_intent.dtype == np.int8

    def test_att_legs_to_shape(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        na = prog.n_attackers
        assert prog.att_legs_to.shape == (na, 3, 2)
        assert prog.att_legs_to.dtype == np.float64

    def test_att_legs_trigger_shape_dtype(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        na = prog.n_attackers
        assert prog.att_legs_trigger.shape == (na, 3)
        assert prog.att_legs_trigger.dtype == np.int8

    def test_att_legs_delay_shape(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        na = prog.n_attackers
        assert prog.att_legs_delay.shape == (na, 3)
        assert prog.att_legs_delay.dtype == np.float64

    def test_att_n_legs_shape_dtype(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        na = prog.n_attackers
        assert prog.att_n_legs.shape == (na,)
        assert prog.att_n_legs.dtype == np.int64

    def test_def_attr_shape(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        nd = prog.n_defenders
        assert prog.def_attr.shape == (nd, N_ATTR)
        assert prog.def_attr.dtype == np.float64

    def test_def_start_shape(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        nd = prog.n_defenders
        assert prog.def_start.shape == (nd, 2)
        assert prog.def_start.dtype == np.float64

    def test_def_mark_target_shape_dtype(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        nd = prog.n_defenders
        assert prog.def_mark_target.shape == (nd,)
        assert prog.def_mark_target.dtype == np.int64

    def test_kicker_attr_shape(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        assert prog.kicker_attr.shape == (N_ATTR,)
        assert prog.kicker_attr.dtype == np.float64

    def test_kick_pos_shape(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        assert prog.kick_pos.shape == (2,)
        assert prog.kick_pos.dtype == np.float64

    def test_delivery_target_shape(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        assert prog.delivery_target.shape == (2,)
        assert prog.delivery_target.dtype == np.float64


# ---------------------------------------------------------------------------
# Read-only enforcement
# ---------------------------------------------------------------------------


class TestSimProgramReadOnly:
    def _all_arrays(self, prog: SimProgram) -> list[np.ndarray]:
        return [
            prog.att_attr,
            prog.att_start,
            prog.att_intent,
            prog.att_legs_to,
            prog.att_legs_trigger,
            prog.att_legs_delay,
            prog.att_n_legs,
            prog.def_attr,
            prog.def_start,
            prog.def_mark_target,
            prog.kicker_attr,
            prog.kick_pos,
            prog.delivery_target,
        ]

    def test_all_arrays_read_only(self) -> None:
        prog = compile_scenario(_corner_scenario())
        for arr in self._all_arrays(prog):
            assert not arr.flags.writeable, f"Array {arr} should be read-only but writeable=True"

    def test_writing_raises(self) -> None:
        prog = compile_scenario(_corner_scenario())
        with pytest.raises(ValueError, match="read-only"):
            prog.att_attr[0, 0] = 999.0

    def test_def_mark_target_write_raises(self) -> None:
        prog = compile_scenario(_corner_scenario())
        with pytest.raises(ValueError, match="read-only"):
            prog.def_mark_target[0] = 99

    def test_kick_pos_write_raises(self) -> None:
        prog = compile_scenario(_corner_scenario())
        with pytest.raises(ValueError, match="read-only"):
            prog.kick_pos[0] = 0.0

    def test_all_arrays_c_contiguous(self) -> None:
        prog = compile_scenario(_corner_scenario())
        for arr in self._all_arrays(prog):
            assert arr.flags[
                "C_CONTIGUOUS"
            ], f"Array should be C-contiguous but is not: flags={arr.flags}"


# ---------------------------------------------------------------------------
# Attacker content
# ---------------------------------------------------------------------------


class TestAttackerContent:
    def test_n_attackers_matches_routine_assignments(self) -> None:
        routine = all_corner_routines()[0]
        sc = _corner_scenario(routine=routine)
        prog = compile_scenario(sc)
        assert prog.n_attackers == len(routine.assignments)

    def test_kicker_excluded_from_attackers(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        assert sc.kicker_id not in prog.att_player_ids

    def test_att_player_ids_length(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        assert len(prog.att_player_ids) == prog.n_attackers

    def test_att_player_ids_in_attacking_team(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        att_ids = {p.player_id for p in sc.attacking_team.players}
        for pid in prog.att_player_ids:
            assert pid in att_ids

    def test_unused_legs_are_nan(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        # Legs beyond att_n_legs[i] should be NaN
        for i in range(prog.n_attackers):
            n = int(prog.att_n_legs[i])
            for j in range(n, 3):
                assert np.all(
                    np.isnan(prog.att_legs_to[i, j, :])
                ), f"attacker {i} leg {j} should be NaN (n_legs={n})"

    def test_unused_trigger_slots_are_minus_one(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        for i in range(prog.n_attackers):
            n = int(prog.att_n_legs[i])
            for j in range(n, 3):
                assert prog.att_legs_trigger[i, j] == -1

    def test_att_intent_values_in_range(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        assert np.all(prog.att_intent >= 0)
        assert np.all(prog.att_intent <= 4)


# ---------------------------------------------------------------------------
# Corner kick position
# ---------------------------------------------------------------------------


class TestCornerKickPos:
    def test_right_corner_kick_pos(self) -> None:
        # Ball on the corner arc ~0.3 m inside both lines (see compile_scenario:
        # taking it exactly on the goal-line plane makes inswingers cross out).
        sc = _corner_scenario(corner_side="right")
        prog = compile_scenario(sc)
        assert prog.kick_pos[0] == pytest.approx(52.2)
        assert prog.kick_pos[1] == pytest.approx(-33.7)

    def test_left_corner_kick_pos(self) -> None:
        sc = _corner_scenario(corner_side="left")
        prog = compile_scenario(sc)
        assert prog.kick_pos[0] == pytest.approx(52.2)
        assert prog.kick_pos[1] == pytest.approx(33.7)

    def test_set_piece_code_corner(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        assert prog.set_piece == 0  # 0 = corner


# ---------------------------------------------------------------------------
# Free-kick: wall placement
# ---------------------------------------------------------------------------


class TestFreeKickWall:
    def test_fk_set_piece_code(self) -> None:
        sc = _fk_scenario()
        prog = compile_scenario(sc)
        assert prog.set_piece == 1  # 1 = free_kick

    def test_fk_kick_pos_matches_scenario(self) -> None:
        sc = _fk_scenario(fk_x=30.0, fk_y=5.0)
        prog = compile_scenario(sc)
        assert prog.kick_pos[0] == pytest.approx(30.0)
        assert prog.kick_pos[1] == pytest.approx(5.0)

    def test_wall_defenders_count(self) -> None:
        """Wall defenders are included in defender array; n_defenders = 1 GK + 10 outfielders."""
        sc = _fk_scenario(wall_size=3)
        prog = compile_scenario(sc)
        # GK + 10 outfielders = 11 total
        assert prog.n_defenders == 11

    def test_wall_defenders_9_15m_from_kick_pos(self) -> None:
        """Wall defenders must be 9.15 m from kick_pos toward goal center (52.5, 0)."""
        wall_size = 4
        fk_x, fk_y = 25.0, 8.0
        sc = _fk_scenario(wall_size=wall_size, fk_x=fk_x, fk_y=fk_y)
        prog = compile_scenario(sc)

        kick_pos = np.array([fk_x, fk_y])
        goal_center = np.array([52.5, 0.0])
        to_goal = goal_center - kick_pos
        to_goal_unit = to_goal / np.linalg.norm(to_goal)
        wall_mid = kick_pos + 9.15 * to_goal_unit

        # Wall positions are in def_start[1 : 1+wall_size] (index 0 = GK)
        wall_positions = prog.def_start[1 : 1 + wall_size]
        assert wall_positions.shape == (wall_size, 2)

        # Each wall player should be within 0.5 * (wall_size-1) * 0.4 of wall_mid
        # i.e. all within the wall spread from center
        centroid = np.mean(wall_positions, axis=0)
        dist_from_mid = float(np.linalg.norm(centroid - wall_mid))
        assert (
            dist_from_mid < 0.5
        ), f"Wall centroid {centroid} is {dist_from_mid:.3f} m from expected mid {wall_mid}"

    def test_wall_spacing_04m(self) -> None:
        """Adjacent wall players should be ~0.4 m apart."""
        wall_size = 4
        sc = _fk_scenario(wall_size=wall_size)
        prog = compile_scenario(sc)

        wall_positions = prog.def_start[1 : 1 + wall_size]
        for k in range(wall_size - 1):
            d = float(np.linalg.norm(wall_positions[k + 1] - wall_positions[k]))
            assert d == pytest.approx(
                0.4, abs=0.01
            ), f"Wall spacing between {k} and {k+1}: {d:.4f} m (expected 0.4 m)"

    def test_wall_players_have_minus_one_mark_target(self) -> None:
        """Wall players are zonal (no mark target)."""
        wall_size = 3
        sc = _fk_scenario(wall_size=wall_size)
        prog = compile_scenario(sc)
        # indices 1..wall_size are wall players
        for k in range(1, 1 + wall_size):
            assert prog.def_mark_target[k] == -1


# ---------------------------------------------------------------------------
# Man-marking assignment
# ---------------------------------------------------------------------------


class TestMarkingAssignment:
    def test_marker_targets_are_valid_attacker_indices(self) -> None:
        sc = _corner_scenario(scheme=hybrid())  # 5 markers
        prog = compile_scenario(sc)
        na = prog.n_attackers
        for k in range(prog.n_defenders):
            t = int(prog.def_mark_target[k])
            assert t == -1 or (0 <= t < na), f"def_mark_target[{k}]={t} is invalid (na={na})"

    def test_markers_assigned_to_distinct_attackers(self) -> None:
        """Distinct targets when n_markers <= n_attackers (no wrap-around case)."""
        # zonal_six_two: 2 markers vs 4 attackers — no overflow, must be distinct
        sc = _corner_scenario(scheme=zonal_six_two())
        prog = compile_scenario(sc)
        targets = [int(t) for t in prog.def_mark_target if int(t) >= 0]
        assert len(targets) == len(set(targets)), f"Duplicate mark targets: {targets}"

    def test_gk_is_zonal(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        assert prog.def_mark_target[prog.gk_index] == -1

    def test_gk_index_is_zero(self) -> None:
        sc = _corner_scenario()
        prog = compile_scenario(sc)
        assert prog.gk_index == 0

    def test_markers_goal_side_of_targets(self) -> None:
        """Each marker should be closer to the goal (52.5, 0) than their target attacker."""
        sc = _corner_scenario(scheme=man_marking_heavy())
        prog = compile_scenario(sc)
        goal = np.array([52.5, 0.0])
        # Markers are in def_start after GK. Find all markers (def_mark_target >= 0)
        for k in range(prog.n_defenders):
            t = int(prog.def_mark_target[k])
            if t < 0:
                continue
            marker_pos = prog.def_start[k]
            att_pos = prog.att_start[t]
            marker_dist = float(np.linalg.norm(marker_pos - goal))
            att_dist = float(np.linalg.norm(att_pos - goal))
            # Marker should be between att_pos and goal: closer to goal
            assert marker_dist < att_dist + 1e-6, (
                f"Marker {k} (dist={marker_dist:.2f}) not goal-side of "
                f"attacker {t} (dist={att_dist:.2f})"
            )

    def test_man_marking_heavy_has_eight_markers(self) -> None:
        sc = _corner_scenario(scheme=man_marking_heavy())
        prog = compile_scenario(sc)
        # compile assigns exactly n_man_markers=8 markers (targets may wrap
        # to attacker 0 when markers > attackers, but all 8 are placed)
        marker_count = sum(1 for t in prog.def_mark_target if int(t) >= 0)
        assert marker_count == 8


# ---------------------------------------------------------------------------
# Zonal fill
# ---------------------------------------------------------------------------


class TestZonalFill:
    def test_zonal_defenders_have_minus_one_target(self) -> None:
        sc = _corner_scenario(scheme=zonal_six_two())
        prog = compile_scenario(sc)
        # Zonal defenders: def_mark_target == -1 and not GK
        zonal_indices = [k for k in range(prog.n_defenders) if int(prog.def_mark_target[k]) == -1]
        # Must include at least the GK + zonal outfielders
        assert len(zonal_indices) >= 1

    def test_zonal_positions_match_scheme_points(self) -> None:
        """Zonal outfielders should be placed at scheme.zonal_points coordinates."""
        scheme = zonal_six_two()
        sc = _corner_scenario(scheme=scheme)
        prog = compile_scenario(sc)

        # Find defender positions for zonal players (non-GK, no mark target)
        # The zonal positions in def_start should match the scheme zonal_points
        scheme_coords = {(pt.x, pt.y) for pt in scheme.zonal_points}
        for k in range(prog.n_defenders):
            if k == prog.gk_index:
                continue
            if int(prog.def_mark_target[k]) == -1:
                pos = (float(prog.def_start[k, 0]), float(prog.def_start[k, 1]))
                # Position should match one of the scheme points or GK position
                gk_pos = (scheme.gk_position.x, scheme.gk_position.y)
                if pos != gk_pos:
                    assert (
                        pos in scheme_coords
                    ), f"Zonal defender {k} at {pos} not in scheme points {scheme_coords}"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_scenario_identical_bytes(self) -> None:
        sc = _corner_scenario()
        prog1 = compile_scenario(sc)
        prog2 = compile_scenario(sc)
        # All float arrays must be byte-identical
        np.testing.assert_array_equal(prog1.att_attr, prog2.att_attr)
        np.testing.assert_array_equal(prog1.def_start, prog2.def_start)
        np.testing.assert_array_equal(prog1.att_legs_to, prog2.att_legs_to)
        np.testing.assert_array_equal(prog1.def_mark_target, prog2.def_mark_target)

    def test_tobytes_identical(self) -> None:
        sc = _corner_scenario()
        prog1 = compile_scenario(sc)
        prog2 = compile_scenario(sc)
        assert prog1.att_attr.tobytes() == prog2.att_attr.tobytes()
        assert prog1.def_start.tobytes() == prog2.def_start.tobytes()
        assert prog1.att_intent.tobytes() == prog2.att_intent.tobytes()
        assert prog1.def_mark_target.tobytes() == prog2.def_mark_target.tobytes()


# ---------------------------------------------------------------------------
# Library cross-compilation: every routine x every scheme
# ---------------------------------------------------------------------------


class TestLibraryCrossCompile:
    @pytest.mark.parametrize("routine", all_corner_routines())
    @pytest.mark.parametrize("scheme", all_schemes())
    def test_corner_routine_scheme_compiles(
        self, routine: RoutineSpec, scheme: DefensiveScheme
    ) -> None:
        sc = _corner_scenario(routine=routine, scheme=scheme)
        prog = compile_scenario(sc)
        assert prog.n_attackers == len(routine.assignments)
        assert prog.n_defenders == 11  # GK + 10 outfielders

    def test_direct_free_kick_compiles(self) -> None:
        sc = _fk_scenario(wall_size=3)
        prog = compile_scenario(sc)
        assert prog.set_piece == 1
        assert prog.n_defenders == 11

    @pytest.mark.parametrize("wall_size", [0, 1, 2, 3, 4, 5, 6])
    def test_fk_all_wall_sizes_compile(self, wall_size: int) -> None:
        sc = _fk_scenario(wall_size=wall_size)
        prog = compile_scenario(sc)
        assert prog.n_defenders == 11
        # Check att_intent and att_n_legs are properly shaped
        assert prog.att_intent.shape == (prog.n_attackers,)
        assert prog.att_n_legs.shape == (prog.n_attackers,)

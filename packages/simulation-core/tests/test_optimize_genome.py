"""Pure genome layer: param types, the corner search space, and the
params -> Scenario builder (the optimizer's genome -> phenotype map)."""

import pytest

from restart.optimize.genome import (
    ZONE_GRID,
    CategoricalParam,
    ContinuousParam,
    CornerGenome,
    FreeKickGenome,
    IntParam,
    SearchSpace,
)
from restart.players.demo import demo_team
from restart.players.player import PositionGroup
from restart.tactics.compile import Scenario, compile_scenario
from restart.tactics.library import all_corner_routines, all_schemes, direct_free_kick
from restart.tactics.routine import DeliveryType, Intent, PitchPoint, SetPiece

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


def fk_base_scenario() -> Scenario:
    """A valid FREE_KICK base (fk_position set) for the free-kick genome."""
    routine = direct_free_kick()
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
        fk_position=PitchPoint(x=35.0, y=-20.0),
    )


class TestParamTypes:
    def test_continuous_clips_and_rejects(self) -> None:
        p = ContinuousParam("speed", 16.0, 32.0)
        assert p.validate(24.0) == 24.0
        with pytest.raises(ValueError, match="outside"):
            p.validate(40.0)

    def test_int_accepts_integral_rejects_out_of_range(self) -> None:
        p = IntParam("n", 1, 4)
        assert p.validate(3) == 3
        assert isinstance(p.validate(3.0), int)
        with pytest.raises(ValueError, match="outside"):
            p.validate(5)

    def test_categorical_rejects_unknown_choice(self) -> None:
        p = CategoricalParam("kind", ("a", "b"))
        assert p.validate("a") == "a"
        with pytest.raises(ValueError, match="choice"):
            p.validate("z")


class TestSearchSpace:
    def test_rejects_unknown_param(self) -> None:
        space = SearchSpace((ContinuousParam("x", 0.0, 1.0),))
        with pytest.raises(ValueError, match="unknown"):
            space.validate({"y": 0.5})

    def test_validate_dispatches_per_type(self) -> None:
        space = SearchSpace((ContinuousParam("x", 0.0, 1.0), CategoricalParam("k", ("a", "b"))))
        out = space.validate({"x": 0.3, "k": "b"})
        assert out == {"x": 0.3, "k": "b"}


class TestZoneGrid:
    def test_all_zones_on_pitch(self) -> None:
        # PitchPoint construction enforces on-pitch; this asserts the grid is
        # non-empty and usable as runner targets.
        assert len(ZONE_GRID) >= 5
        for pt in ZONE_GRID.values():
            assert -52.5 <= pt.x <= 52.5


class TestCornerGenome:
    def test_space_dim_in_target_band(self) -> None:
        space = CornerGenome().space
        # Medium genome: ~10-15 dims (doc 06 sec3.1).
        assert 10 <= len(space.params) <= 17

    def test_defaults_compile(self) -> None:
        g = CornerGenome()
        scn = g.to_scenario(base_scenario(), g.defaults())
        # Builds a valid, compilable Scenario (no exception == feasible).
        prog = compile_scenario(scn)
        assert prog.n_attackers == g.n_runners

    def test_delivery_type_categorical_applied(self) -> None:
        g = CornerGenome()
        v = {**g.defaults(), "delivery_type": "outswinger"}
        scn = g.to_scenario(base_scenario(), v)
        assert scn.routine.delivery.type is DeliveryType.OUTSWINGER

    def test_runner_zone_maps_to_final_leg_target(self) -> None:
        g = CornerGenome()
        v = {**g.defaults(), "r1_zone": "far_post"}
        scn = g.to_scenario(base_scenario(), v)
        far = ZONE_GRID["far_post"]
        runner1 = scn.routine.assignments[1]
        assert runner1.runs[-1].to.x == far.x
        assert runner1.runs[-1].to.y == far.y

    def test_lead_attacker_fixed_guarantees_feasibility(self) -> None:
        g = CornerGenome(fixed_lead_attacker=True)
        scn = g.to_scenario(base_scenario(), g.defaults())
        assert any(a.intent is Intent.ATTACK_BALL for a in scn.routine.assignments)

    def test_infeasible_genome_raises(self) -> None:
        # Free intents with no attack_ball -> CORNER non-short validation rejects.
        g = CornerGenome(fixed_lead_attacker=False)
        v = {**g.defaults()}
        for i in range(g.n_runners):
            v[f"r{i}_intent"] = "decoy"
        with pytest.raises(ValueError):
            g.to_scenario(base_scenario(), v)


class TestPhase8Realism:
    """Scenario realism: off-ball zones + a wider attacker template."""

    def test_off_ball_zones_present_and_on_pitch(self) -> None:
        # Not every runner should attack the 6-yard box; off-ball zones give the
        # optimizer lurk / recycle / half-space options.
        for name in ("top_of_box", "left_half_space", "right_half_space", "deep_recycle"):
            assert name in ZONE_GRID
            pt = ZONE_GRID[name]  # constructs a valid (on-pitch) PitchPoint
            assert -52.5 <= pt.x <= 52.5

    def test_corner_template_supports_seven_attackers(self) -> None:
        g = CornerGenome(n_runners=6)  # kicker + 6 runners = 7 attackers
        scn = g.to_scenario(base_scenario(), g.defaults())
        assert len(scn.routine.assignments) == 6
        assert compile_scenario(scn).n_attackers == 6

    def test_template_cap_is_seven_runners(self) -> None:
        CornerGenome(n_runners=7)  # at the template ceiling: allowed
        with pytest.raises(ValueError, match="n_runners"):
            CornerGenome(n_runners=8)

    def test_off_ball_zone_maps_to_runner_target(self) -> None:
        g = CornerGenome(n_runners=6)
        v = {**g.defaults(), "r5_zone": "deep_recycle"}
        scn = g.to_scenario(base_scenario(), v)
        recycle = ZONE_GRID["deep_recycle"]
        last_leg = scn.routine.assignments[5].runs[-1]
        assert (last_leg.to.x, last_leg.to.y) == (recycle.x, recycle.y)


class TestFreeKickGenome:
    """Phase 8: a basic free-kick genome over the existing FK engine scaffolding
    (offside / off-ball runner timing deferred to O-3)."""

    def test_builds_free_kick_scenario(self) -> None:
        g = FreeKickGenome(n_runners=4)
        scn = g.to_scenario(fk_base_scenario(), g.defaults())
        assert scn.routine.set_piece is SetPiece.FREE_KICK
        assert scn.fk_position is not None
        assert len(scn.routine.assignments) == 4
        assert compile_scenario(scn).n_attackers == 4

    def test_requires_fk_position(self) -> None:
        # A corner base has no fk_position; building a free kick from it must fail.
        g = FreeKickGenome()
        with pytest.raises(ValueError):
            g.to_scenario(base_scenario(), g.defaults())

    def test_delivery_params_applied(self) -> None:
        g = FreeKickGenome(n_runners=4)
        v = {**g.defaults(), "delivery_type": "driven", "speed_ms": 27.0}
        scn = g.to_scenario(fk_base_scenario(), v)
        assert scn.routine.delivery.type is DeliveryType.DRIVEN
        assert scn.routine.delivery.speed_ms == 27.0

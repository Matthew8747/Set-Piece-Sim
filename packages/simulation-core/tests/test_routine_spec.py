"""Tests for RoutineSpec rs/1.0 - validation rules per ADR-004 d2.

All validation must reject; no silent repairs.
"""

import pytest
from pydantic import ValidationError

from restart.tactics.routine import (
    INTENT_CODES,
    TRIGGER_CODES,
    Assignment,
    Delivery,
    DeliveryType,
    Intent,
    PitchPoint,
    RoutineSpec,
    RunLeg,
    SetPiece,
    Trigger,
)

# ---------------------------------------------------------------------------
# Helpers - minimal valid objects
# ---------------------------------------------------------------------------


def _valid_delivery(
    dtype: DeliveryType = DeliveryType.INSWINGER,
    target: PitchPoint | None = None,
) -> Delivery:
    if target is None:
        target = PitchPoint(x=50.0, y=0.0)
    return Delivery(type=dtype, target=target, speed_ms=24.0, spin_rps=8.0)


def _attack_assignment(role: str = "runner_a", start: PitchPoint | None = None) -> Assignment:
    if start is None:
        start = PitchPoint(x=40.0, y=0.0)
    return Assignment(
        role=role,
        start=start,
        runs=(RunLeg(to=PitchPoint(x=50.0, y=0.0), trigger=Trigger.KICK, delay_s=0.0),),
        intent=Intent.ATTACK_BALL,
    )


def _minimal_corner() -> RoutineSpec:
    return RoutineSpec(
        set_piece=SetPiece.CORNER,
        name="test_corner",
        delivery=_valid_delivery(),
        assignments=(_attack_assignment(),),
    )


# ---------------------------------------------------------------------------
# PitchPoint validation
# ---------------------------------------------------------------------------


class TestPitchPoint:
    def test_valid_center(self) -> None:
        p = PitchPoint(x=0.0, y=0.0)
        assert p.x == 0.0
        assert p.y == 0.0

    def test_valid_boundary_x_max(self) -> None:
        p = PitchPoint(x=52.5, y=0.0)
        assert p.x == 52.5

    def test_valid_boundary_y_max(self) -> None:
        p = PitchPoint(x=0.0, y=34.0)
        assert p.y == 34.0

    def test_valid_corner_right(self) -> None:
        PitchPoint(x=52.5, y=-34.0)

    def test_valid_corner_left(self) -> None:
        PitchPoint(x=52.5, y=34.0)

    def test_off_pitch_x_too_large(self) -> None:
        with pytest.raises(ValidationError, match="off-pitch"):
            PitchPoint(x=53.0, y=0.0)

    def test_off_pitch_x_too_small(self) -> None:
        with pytest.raises(ValidationError, match="off-pitch"):
            PitchPoint(x=-53.0, y=0.0)

    def test_off_pitch_y_too_large(self) -> None:
        with pytest.raises(ValidationError, match="off-pitch"):
            PitchPoint(x=0.0, y=35.0)

    def test_off_pitch_y_too_small(self) -> None:
        with pytest.raises(ValidationError, match="off-pitch"):
            PitchPoint(x=0.0, y=-34.5)

    def test_as_array_shape(self) -> None:
        import numpy as np

        p = PitchPoint(x=10.0, y=-5.0)
        arr = p.as_array()
        assert arr.shape == (2,)
        assert arr.dtype == np.float64
        assert arr[0] == 10.0
        assert arr[1] == -5.0

    def test_frozen(self) -> None:
        # pydantic v2 frozen models raise ValidationError on direct attribute assignment
        p = PitchPoint(x=10.0, y=5.0)
        with pytest.raises(ValidationError):
            p.x = 99.0  # type: ignore[misc]

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            PitchPoint(x=0.0, y=0.0, z=0.0)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Delivery validation
# ---------------------------------------------------------------------------


class TestDelivery:
    def test_valid(self) -> None:
        d = _valid_delivery()
        assert d.speed_ms == 24.0

    def test_speed_too_low(self) -> None:
        with pytest.raises(ValidationError):
            Delivery(
                type=DeliveryType.INSWINGER,
                target=PitchPoint(x=50.0, y=0.0),
                speed_ms=9.0,
                spin_rps=8.0,
            )

    def test_speed_too_high(self) -> None:
        with pytest.raises(ValidationError):
            Delivery(
                type=DeliveryType.INSWINGER,
                target=PitchPoint(x=50.0, y=0.0),
                speed_ms=36.0,
                spin_rps=8.0,
            )

    def test_spin_negative(self) -> None:
        with pytest.raises(ValidationError):
            Delivery(
                type=DeliveryType.INSWINGER,
                target=PitchPoint(x=50.0, y=0.0),
                speed_ms=24.0,
                spin_rps=-1.0,
            )

    def test_spin_too_high(self) -> None:
        with pytest.raises(ValidationError):
            Delivery(
                type=DeliveryType.INSWINGER,
                target=PitchPoint(x=50.0, y=0.0),
                speed_ms=24.0,
                spin_rps=13.0,
            )

    def test_off_pitch_target_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Delivery(
                type=DeliveryType.INSWINGER,
                target=PitchPoint(x=55.0, y=0.0),  # off-pitch
                speed_ms=24.0,
                spin_rps=8.0,
            )

    def test_frozen(self) -> None:
        # pydantic v2 frozen models raise ValidationError on direct attribute assignment
        d = _valid_delivery()
        with pytest.raises(ValidationError):
            d.speed_ms = 99.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Assignment validation
# ---------------------------------------------------------------------------


class TestAssignment:
    def test_valid(self) -> None:
        a = _attack_assignment()
        assert a.role == "runner_a"

    def test_role_whitespace_rejected(self) -> None:
        with pytest.raises(ValidationError, match="whitespace"):
            Assignment(
                role="near post",  # space in role name
                start=PitchPoint(x=40.0, y=0.0),
                runs=(),
                intent=Intent.ATTACK_BALL,
            )

    def test_role_tab_rejected(self) -> None:
        with pytest.raises(ValidationError, match="whitespace"):
            Assignment(
                role="near\tpost",
                start=PitchPoint(x=40.0, y=0.0),
                runs=(),
                intent=Intent.ATTACK_BALL,
            )

    def test_role_max_length(self) -> None:
        # 32 chars ok
        Assignment(
            role="a" * 32,
            start=PitchPoint(x=40.0, y=0.0),
            runs=(),
            intent=Intent.ATTACK_BALL,
        )

    def test_role_too_long(self) -> None:
        with pytest.raises(ValidationError):
            Assignment(
                role="a" * 33,
                start=PitchPoint(x=40.0, y=0.0),
                runs=(),
                intent=Intent.ATTACK_BALL,
            )

    def test_too_many_legs_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Assignment(
                role="runner",
                start=PitchPoint(x=40.0, y=0.0),
                runs=(
                    RunLeg(to=PitchPoint(x=45.0, y=0.0)),
                    RunLeg(to=PitchPoint(x=48.0, y=0.0)),
                    RunLeg(to=PitchPoint(x=50.0, y=0.0)),
                    RunLeg(to=PitchPoint(x=52.0, y=0.0)),  # 4th leg = too many
                ),
                intent=Intent.ATTACK_BALL,
            )

    def test_off_pitch_start_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Assignment(
                role="runner",
                start=PitchPoint(x=60.0, y=0.0),  # off-pitch
                runs=(),
                intent=Intent.ATTACK_BALL,
            )


# ---------------------------------------------------------------------------
# RunLeg validation
# ---------------------------------------------------------------------------


class TestRunLeg:
    def test_valid_defaults(self) -> None:
        leg = RunLeg(to=PitchPoint(x=50.0, y=0.0))
        assert leg.trigger == Trigger.KICK
        assert leg.delay_s == 0.0

    def test_delay_too_high(self) -> None:
        with pytest.raises(ValidationError):
            RunLeg(to=PitchPoint(x=50.0, y=0.0), delay_s=3.0)

    def test_delay_negative(self) -> None:
        with pytest.raises(ValidationError):
            RunLeg(to=PitchPoint(x=50.0, y=0.0), delay_s=-0.1)

    def test_all_triggers(self) -> None:
        for t in Trigger:
            leg = RunLeg(to=PitchPoint(x=50.0, y=0.0), trigger=t)
            assert leg.trigger == t


# ---------------------------------------------------------------------------
# RoutineSpec validation
# ---------------------------------------------------------------------------


class TestRoutineSpec:
    def test_valid_corner(self) -> None:
        spec = _minimal_corner()
        assert spec.spec_version == "rs/1.0"
        assert spec.set_piece == SetPiece.CORNER

    def test_frozen(self) -> None:
        # pydantic v2 frozen models raise ValidationError on direct attribute assignment
        spec = _minimal_corner()
        with pytest.raises(ValidationError):
            spec.name = "hacked"  # type: ignore[misc]

    def test_duplicate_roles_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate roles"):
            RoutineSpec(
                set_piece=SetPiece.CORNER,
                name="dup_test",
                delivery=_valid_delivery(),
                assignments=(
                    _attack_assignment("runner_a"),
                    _attack_assignment("runner_a"),  # duplicate
                ),
            )

    def test_no_attack_ball_non_short_rejected(self) -> None:
        with pytest.raises(ValidationError, match="ATTACK_BALL"):
            RoutineSpec(
                set_piece=SetPiece.CORNER,
                name="no_attack_ball",
                delivery=_valid_delivery(DeliveryType.INSWINGER),
                assignments=(
                    Assignment(
                        role="decoy_only",
                        start=PitchPoint(x=40.0, y=0.0),
                        runs=(),
                        intent=Intent.DECOY,
                    ),
                ),
            )

    def test_no_attack_ball_short_ok(self) -> None:
        # SHORT delivery exempts ATTACK_BALL requirement
        spec = RoutineSpec(
            set_piece=SetPiece.CORNER,
            name="short_no_attack",
            delivery=Delivery(
                type=DeliveryType.SHORT,
                target=PitchPoint(x=47.0, y=-28.0),
                speed_ms=12.0,
                spin_rps=0.0,
            ),
            assignments=(
                Assignment(
                    role="short_option",
                    start=PitchPoint(x=44.0, y=-25.0),
                    runs=(),
                    intent=Intent.SHORT_OPTION,
                ),
            ),
        )
        assert spec.delivery.type == DeliveryType.SHORT

    def test_corner_target_too_deep_rejected(self) -> None:
        # target x <= 26.25 should be rejected for CORNER
        with pytest.raises(ValidationError, match="attacking quarter"):
            RoutineSpec(
                set_piece=SetPiece.CORNER,
                name="bad_target",
                delivery=Delivery(
                    type=DeliveryType.INSWINGER,
                    target=PitchPoint(x=20.0, y=0.0),  # too deep
                    speed_ms=24.0,
                    spin_rps=8.0,
                ),
                assignments=(_attack_assignment(),),
            )

    def test_corner_target_exactly_at_boundary_rejected(self) -> None:
        with pytest.raises(ValidationError, match="attacking quarter"):
            RoutineSpec(
                set_piece=SetPiece.CORNER,
                name="boundary_test",
                delivery=Delivery(
                    type=DeliveryType.INSWINGER,
                    target=PitchPoint(x=26.25, y=0.0),  # exactly at boundary = rejected
                    speed_ms=24.0,
                    spin_rps=8.0,
                ),
                assignments=(_attack_assignment(),),
            )

    def test_corner_target_just_past_boundary_ok(self) -> None:
        spec = RoutineSpec(
            set_piece=SetPiece.CORNER,
            name="valid_target",
            delivery=Delivery(
                type=DeliveryType.INSWINGER,
                target=PitchPoint(x=26.26, y=0.0),  # just past = ok
                speed_ms=24.0,
                spin_rps=8.0,
            ),
            assignments=(_attack_assignment(),),
        )
        assert spec.delivery.target.x == 26.26

    def test_free_kick_no_target_restriction(self) -> None:
        # FK can have any valid pitch point as delivery target
        spec = RoutineSpec(
            set_piece=SetPiece.FREE_KICK,
            name="fk_test",
            delivery=Delivery(
                type=DeliveryType.DRIVEN,
                target=PitchPoint(x=51.5, y=1.5),
                speed_ms=28.0,
                spin_rps=3.0,
            ),
            assignments=(
                Assignment(
                    role="rebounder",
                    start=PitchPoint(x=39.0, y=0.0),
                    runs=(),
                    intent=Intent.SECOND_BALL,
                ),
            ),
        )
        assert spec.set_piece == SetPiece.FREE_KICK

    def test_too_few_assignments_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RoutineSpec(
                set_piece=SetPiece.CORNER,
                name="empty",
                delivery=_valid_delivery(),
                assignments=(),  # min_length=1
            )

    def test_too_many_assignments_rejected(self) -> None:
        assignments = tuple(_attack_assignment(f"runner_{i}") for i in range(7))  # max_length=6
        with pytest.raises(ValidationError):
            RoutineSpec(
                set_piece=SetPiece.CORNER,
                name="too_many",
                delivery=_valid_delivery(),
                assignments=assignments,
            )

    def test_six_assignments_ok(self) -> None:
        assignments = tuple(_attack_assignment(f"runner_{i}") for i in range(6))  # max_length=6
        spec = RoutineSpec(
            set_piece=SetPiece.CORNER,
            name="max_assignments",
            delivery=_valid_delivery(),
            assignments=assignments,
        )
        assert len(spec.assignments) == 6


# ---------------------------------------------------------------------------
# Code mapping exports
# ---------------------------------------------------------------------------


class TestCodeMappings:
    def test_intent_codes_cover_all_intents(self) -> None:
        for intent in Intent:
            assert intent in INTENT_CODES

    def test_intent_codes_are_consecutive(self) -> None:
        codes = sorted(INTENT_CODES.values())
        assert codes == list(range(len(Intent)))

    def test_trigger_codes_cover_all_triggers(self) -> None:
        for trigger in Trigger:
            assert trigger in TRIGGER_CODES

    def test_trigger_codes_are_consecutive(self) -> None:
        codes = sorted(TRIGGER_CODES.values())
        assert codes == list(range(len(Trigger)))

    def test_attack_ball_is_zero(self) -> None:
        assert INTENT_CODES[Intent.ATTACK_BALL] == 0

    def test_kick_approach_is_zero(self) -> None:
        assert TRIGGER_CODES[Trigger.KICK_APPROACH] == 0

    def test_kick_is_one(self) -> None:
        assert TRIGGER_CODES[Trigger.KICK] == 1

    def test_ball_apex_is_two(self) -> None:
        assert TRIGGER_CODES[Trigger.BALL_APEX] == 2

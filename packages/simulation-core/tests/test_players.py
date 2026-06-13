"""Tests for restart.players — attributes, player, team, and demo data."""

import numpy as np
import pytest

from restart.players.attributes import ATTR_COLUMNS, N_ATTR, Attr, PlayerAttributes
from restart.players.demo import demo_team
from restart.players.player import Player, PositionGroup
from restart.players.team import Team

# ---------------------------------------------------------------------------
# PlayerAttributes
# ---------------------------------------------------------------------------


class TestPlayerAttributesBounds:
    """Bounds validation: out-of-range values must be rejected."""

    @pytest.mark.parametrize(
        "field,bad_value",
        [
            ("top_speed_ms", 5.0),  # below ge=5.5
            ("top_speed_ms", 10.0),  # above le=9.8
            ("accel_ms2", 1.5),  # below ge=2.0
            ("accel_ms2", 8.5),  # above le=8.0
            ("reaction_time_s", 0.10),  # below ge=0.15
            ("reaction_time_s", 0.50),  # above le=0.45
            ("agility", -0.1),  # below ge=0.0
            ("agility", 1.1),  # above le=1.0
            ("jump_reach_m", 2.0),  # below ge=2.10
            ("jump_reach_m", 3.1),  # above le=3.00
            ("heading", -0.01),
            ("heading", 1.01),
            ("strength", -0.01),
            ("strength", 1.01),
            ("marking", -0.01),
            ("marking", 1.01),
            ("awareness_off", -0.01),
            ("awareness_off", 1.01),
            ("awareness_def", -0.01),
            ("awareness_def", 1.01),
            ("delivery", -0.01),
            ("delivery", 1.01),
            ("height_m", 1.59),  # below ge=1.60
            ("height_m", 2.11),  # above le=2.10
        ],
    )
    def test_out_of_range_rejected(self, field: str, bad_value: float) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PlayerAttributes(**{field: bad_value})

    def test_defaults_are_valid(self) -> None:
        attrs = PlayerAttributes()
        assert attrs.top_speed_ms == 7.8

    def test_boundary_values_accepted(self) -> None:
        """Exact boundary values should be accepted (ge/le not gt/lt)."""
        attrs = PlayerAttributes(
            top_speed_ms=5.5,
            accel_ms2=2.0,
            reaction_time_s=0.15,
            agility=0.0,
            jump_reach_m=2.10,
            heading=0.0,
            strength=0.0,
            marking=0.0,
            awareness_off=0.0,
            awareness_def=0.0,
            delivery=0.0,
            height_m=1.60,
        )
        assert attrs.top_speed_ms == 5.5


class TestPlayerAttributesFrozen:
    """Frozen model: mutation must raise."""

    def test_mutation_raises(self) -> None:
        from pydantic import ValidationError

        attrs = PlayerAttributes()
        with pytest.raises(ValidationError):
            attrs.top_speed_ms = 9.0  # type: ignore[misc]

    def test_extra_fields_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PlayerAttributes(unknown_field=1.0)  # type: ignore[call-arg]


class TestPlayerAttributesToRow:
    """to_row() column order must match Attr enum."""

    def test_column_order_matches_attr_enum(self) -> None:
        attrs = PlayerAttributes(
            top_speed_ms=8.5,
            accel_ms2=6.0,
            reaction_time_s=0.20,
            agility=0.7,
            jump_reach_m=2.80,
            heading=0.8,
            strength=0.6,
            marking=0.4,
            awareness_off=0.9,
            awareness_def=0.3,
            delivery=0.95,
            height_m=1.90,
        )
        row = attrs.to_row()
        assert row.dtype == np.float64
        assert row.shape == (N_ATTR,)
        assert row[Attr.TOP_SPEED] == pytest.approx(8.5)
        assert row[Attr.ACCEL] == pytest.approx(6.0)
        assert row[Attr.REACTION_TIME] == pytest.approx(0.20)
        assert row[Attr.AGILITY] == pytest.approx(0.7)
        assert row[Attr.JUMP_REACH] == pytest.approx(2.80)
        assert row[Attr.HEADING] == pytest.approx(0.8)
        assert row[Attr.STRENGTH] == pytest.approx(0.6)
        assert row[Attr.MARKING] == pytest.approx(0.4)
        assert row[Attr.AWARENESS_OFF] == pytest.approx(0.9)
        assert row[Attr.AWARENESS_DEF] == pytest.approx(0.3)
        assert row[Attr.DELIVERY] == pytest.approx(0.95)
        assert row[Attr.HEIGHT] == pytest.approx(1.90)

    def test_attr_column_names_match_attr_enum(self) -> None:
        """ATTR_COLUMNS tuple should match Attr enum member names in order."""
        assert len(ATTR_COLUMNS) == len(Attr)
        for attr, col_name in zip(Attr, ATTR_COLUMNS, strict=True):
            assert col_name == attr.name.lower()

    def test_n_attr_equals_12(self) -> None:
        assert N_ATTR == 12


# ---------------------------------------------------------------------------
# Team validators
# ---------------------------------------------------------------------------


def _make_player(pid: str, pos: PositionGroup) -> Player:
    return Player(
        player_id=pid,
        display_name=f"Player {pid}",
        position_group=pos,
        attributes=PlayerAttributes(),
    )


def _squad_11() -> tuple[Player, ...]:
    """Minimal valid 11-player squad: 1 GK + 10 DF."""
    players = [
        _make_player(f"P{i:02d}", PositionGroup.GK if i == 0 else PositionGroup.DF)
        for i in range(11)
    ]
    return tuple(players)


class TestTeamValidators:
    def test_valid_team_created(self) -> None:
        team = Team(team_id="TST", name="Test FC", players=_squad_11())
        assert len(team.players) == 11

    def test_fewer_than_11_players_rejected(self) -> None:
        from pydantic import ValidationError

        players = tuple(
            _make_player(f"P{i:02d}", PositionGroup.DF if i > 0 else PositionGroup.GK)
            for i in range(10)
        )
        with pytest.raises(ValidationError):
            Team(team_id="TST", name="Test FC", players=players)

    def test_duplicate_ids_rejected(self) -> None:
        players = list(_squad_11())
        players[5] = _make_player("P00", PositionGroup.DF)  # duplicate ID
        with pytest.raises(ValueError, match="duplicate"):
            Team(team_id="TST", name="Test FC", players=tuple(players))

    def test_no_goalkeeper_rejected(self) -> None:
        players = tuple(_make_player(f"P{i:02d}", PositionGroup.DF) for i in range(11))
        with pytest.raises(ValueError, match="goalkeeper"):
            Team(team_id="TST", name="Test FC", players=players)

    def test_frozen_team(self) -> None:
        from pydantic import ValidationError

        team = Team(team_id="TST", name="Test FC", players=_squad_11())
        with pytest.raises(ValidationError):
            team.team_id = "OTHER"  # type: ignore[misc]


class TestTeamAttributeMatrix:
    def test_attribute_matrix_ordering(self) -> None:
        """attribute_matrix rows must follow the provided player_ids order."""
        players = [
            _make_player("A", PositionGroup.GK),
            _make_player("B", PositionGroup.DF),
            _make_player("C", PositionGroup.MF),
        ] + [_make_player(f"X{i}", PositionGroup.DF) for i in range(8)]
        team = Team(team_id="T1", name="T1", players=tuple(players))

        mat = team.attribute_matrix(["C", "A", "B"])
        assert mat.shape == (3, N_ATTR)
        # Row 0 should be player C's attributes
        np.testing.assert_array_equal(mat[0], players[2].attributes.to_row())
        # Row 1 should be player A's attributes
        np.testing.assert_array_equal(mat[1], players[0].attributes.to_row())

    def test_missing_player_id_raises(self) -> None:
        team = Team(team_id="T1", name="T1", players=_squad_11())
        with pytest.raises(ValueError, match="not in team"):
            team.attribute_matrix(["DOES_NOT_EXIST"])

    def test_matrix_dtype_float64(self) -> None:
        team = Team(team_id="T1", name="T1", players=_squad_11())
        ids = [p.player_id for p in team.players]
        mat = team.attribute_matrix(ids)
        assert mat.dtype == np.float64


# ---------------------------------------------------------------------------
# demo_team
# ---------------------------------------------------------------------------


class TestDemoTeam:
    def test_deterministic_same_seed(self) -> None:
        """Same seed produces identical attribute rows."""
        t1 = demo_team("TST", "Test FC", seed=42)
        t2 = demo_team("TST", "Test FC", seed=42)
        ids = [p.player_id for p in t1.players]
        np.testing.assert_array_equal(
            t1.attribute_matrix(ids),
            t2.attribute_matrix(ids),
        )

    def test_different_seed_different_squad(self) -> None:
        t1 = demo_team("TST", "Test FC", seed=1)
        t2 = demo_team("TST", "Test FC", seed=2)
        ids = [p.player_id for p in t1.players]
        mat1 = t1.attribute_matrix(ids)
        mat2 = t2.attribute_matrix(ids)
        assert not np.array_equal(mat1, mat2)

    def test_valid_team_validators_pass(self) -> None:
        """Team should pass all pydantic validators without errors."""
        team = demo_team("HOM", "Home FC", seed=0)
        assert team.team_id == "HOM"

    def test_exactly_11_players(self) -> None:
        team = demo_team("T", "T FC", seed=7)
        assert len(team.players) == 11

    def test_exactly_one_goalkeeper(self) -> None:
        team = demo_team("T", "T FC", seed=3)
        gk_count = sum(1 for p in team.players if p.position_group is PositionGroup.GK)
        assert gk_count == 1

    def test_has_kicker_with_delivery_ge_08(self) -> None:
        team = demo_team("T", "T FC", seed=5)
        deliveries = [p.attributes.delivery for p in team.players]
        assert any(
            d >= 0.8 for d in deliveries
        ), f"No player with delivery >= 0.8; deliveries: {deliveries}"

    def test_player_ids_prefixed_with_team_id(self) -> None:
        team = demo_team("XYZ", "XYZ FC", seed=10)
        for p in team.players:
            assert p.player_id.startswith("XYZ-")

    def test_all_attributes_within_bounds(self) -> None:
        """All generated attributes must pass PlayerAttributes validation."""
        team = demo_team("T", "T FC", seed=99)
        # If any attribute were out of bounds, pydantic would have raised during Team construction
        assert len(team.players) == 11

    def test_squad_composition(self) -> None:
        """1 GK + 4 DF + 4 MF + 2 FW."""
        team = demo_team("T", "T FC", seed=20)
        counts = dict.fromkeys(PositionGroup, 0)
        for p in team.players:
            counts[p.position_group] += 1
        assert counts[PositionGroup.GK] == 1
        assert counts[PositionGroup.DF] == 4
        assert counts[PositionGroup.MF] == 4
        assert counts[PositionGroup.FW] == 2

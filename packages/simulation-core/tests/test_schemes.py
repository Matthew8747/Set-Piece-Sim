"""Tests for DefensiveScheme and the library scheme collection."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from restart.domain.pitch import is_on_pitch
from restart.tactics.library import all_schemes, hybrid, man_marking_heavy, zonal_six_two
from restart.tactics.routine import PitchPoint
from restart.tactics.scheme import DefensiveScheme

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scheme_total(s: DefensiveScheme) -> int:
    return len(s.zonal_points) + s.n_man_markers + s.wall_size


# ---------------------------------------------------------------------------
# DefensiveScheme validation
# ---------------------------------------------------------------------------


class TestDefensiveSchemeValidation:
    def test_valid_scheme_accepted(self) -> None:
        s = DefensiveScheme(
            name="test",
            zonal_points=(
                PitchPoint(x=50.0, y=0.0),
                PitchPoint(x=48.0, y=2.0),
            ),
            n_man_markers=8,
            wall_size=0,
        )
        assert _scheme_total(s) == 10

    def test_total_not_ten_rejected(self) -> None:
        with pytest.raises(ValidationError, match="10"):
            DefensiveScheme(
                name="bad",
                zonal_points=(PitchPoint(x=50.0, y=0.0),),
                n_man_markers=3,
                wall_size=0,
                # 1 + 3 + 0 = 4 != 10
            )

    def test_total_eleven_rejected(self) -> None:
        with pytest.raises(ValidationError, match="10"):
            DefensiveScheme(
                name="bad",
                zonal_points=tuple(PitchPoint(x=50.0, y=float(i)) for i in range(5)),
                n_man_markers=5,
                wall_size=1,
                # 5 + 5 + 1 = 11 != 10
            )

    def test_wall_only_scheme(self) -> None:
        s = DefensiveScheme(
            name="wall_heavy",
            zonal_points=(PitchPoint(x=44.0, y=0.0),),
            n_man_markers=3,
            wall_size=6,
        )
        assert _scheme_total(s) == 10

    def test_all_zonal_scheme(self) -> None:
        s = DefensiveScheme(
            name="all_zonal",
            zonal_points=tuple(PitchPoint(x=50.0, y=float(i - 5)) for i in range(10)),
            n_man_markers=0,
            wall_size=0,
        )
        assert _scheme_total(s) == 10

    def test_all_man_marking_scheme(self) -> None:
        # max n_man_markers=8; need 2 zonal to reach 10 (le=8 constraint)
        s = DefensiveScheme(
            name="all_man",
            zonal_points=(
                PitchPoint(x=50.0, y=0.0),
                PitchPoint(x=48.0, y=0.0),
            ),
            n_man_markers=8,
            wall_size=0,
        )
        assert _scheme_total(s) == 10

    def test_negative_markers_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DefensiveScheme(
                name="bad",
                zonal_points=tuple(PitchPoint(x=50.0, y=float(i)) for i in range(10)),
                n_man_markers=-1,
                wall_size=0,
            )

    def test_wall_size_too_large_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DefensiveScheme(
                name="bad",
                zonal_points=(),
                n_man_markers=3,
                wall_size=7,  # max is 6
            )

    def test_frozen(self) -> None:
        s = DefensiveScheme(
            name="test",
            zonal_points=(),
            n_man_markers=10,
            wall_size=0,
        )
        with pytest.raises(ValidationError):
            s.name = "mutated"  # type: ignore[misc]

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            DefensiveScheme(  # type: ignore[call-arg]
                name="test",
                zonal_points=(),
                n_man_markers=10,
                wall_size=0,
                unknown_field=99,
            )

    def test_gk_position_default(self) -> None:
        s = DefensiveScheme(name="test", zonal_points=(), n_man_markers=10, wall_size=0)
        assert s.gk_position.x == pytest.approx(51.5)
        assert s.gk_position.y == pytest.approx(0.0)

    def test_custom_gk_position(self) -> None:
        s = DefensiveScheme(
            name="test",
            zonal_points=(),
            n_man_markers=10,
            wall_size=0,
            gk_position=PitchPoint(x=50.0, y=1.5),
        )
        assert s.gk_position.x == pytest.approx(50.0)

    def test_gk_position_on_pitch(self) -> None:
        s = DefensiveScheme(name="test", zonal_points=(), n_man_markers=10, wall_size=0)
        assert is_on_pitch(s.gk_position.x, s.gk_position.y)


# ---------------------------------------------------------------------------
# Library schemes: sum to 10 outfielders
# ---------------------------------------------------------------------------


class TestLibrarySchemes:
    def test_zonal_six_two_sum_ten(self) -> None:
        s = zonal_six_two()
        assert _scheme_total(s) == 10

    def test_man_marking_heavy_sum_ten(self) -> None:
        s = man_marking_heavy()
        assert _scheme_total(s) == 10

    def test_hybrid_sum_ten(self) -> None:
        s = hybrid()
        assert _scheme_total(s) == 10

    def test_all_schemes_returns_three(self) -> None:
        schemes = all_schemes()
        assert len(schemes) == 3

    def test_all_schemes_all_sum_ten(self) -> None:
        for s in all_schemes():
            assert _scheme_total(s) == 10, f"scheme {s.name!r} does not sum to 10"

    def test_all_schemes_names_unique(self) -> None:
        schemes = all_schemes()
        names = [s.name for s in schemes]
        assert len(set(names)) == len(names)

    def test_zonal_six_two_has_eight_zonal(self) -> None:
        s = zonal_six_two()
        assert len(s.zonal_points) == 8
        assert s.n_man_markers == 2
        assert s.wall_size == 0

    def test_man_marking_heavy_has_eight_markers(self) -> None:
        s = man_marking_heavy()
        assert s.n_man_markers == 8
        assert len(s.zonal_points) == 2
        assert s.wall_size == 0

    def test_hybrid_five_five(self) -> None:
        s = hybrid()
        assert len(s.zonal_points) == 5
        assert s.n_man_markers == 5
        assert s.wall_size == 0

    def test_all_zonal_points_on_pitch(self) -> None:
        for s in all_schemes():
            for pt in s.zonal_points:
                assert is_on_pitch(
                    pt.x, pt.y
                ), f"scheme {s.name!r}: zonal point ({pt.x}, {pt.y}) off-pitch"

    def test_gk_position_on_pitch(self) -> None:
        for s in all_schemes():
            assert is_on_pitch(
                s.gk_position.x, s.gk_position.y
            ), f"scheme {s.name!r}: GK position ({s.gk_position.x}, {s.gk_position.y}) off-pitch"

    def test_corner_schemes_have_wall_size_zero(self) -> None:
        """Library corner schemes must have wall_size=0 (no wall on corners)."""
        for s in all_schemes():
            assert (
                s.wall_size == 0
            ), f"scheme {s.name!r}: wall_size={s.wall_size} (expected 0 for corner use)"

    @pytest.mark.parametrize(
        "combos",
        [
            (5, 3, 3),  # 11 total
            (3, 3, 5),  # 11 total
            (0, 0, 9),  # 9 total
            (10, 0, 1),  # 11 total, also hits zonal max
        ],
    )
    def test_invalid_combos_rejected(self, combos: tuple[int, int, int]) -> None:
        n_zonal, n_markers, n_wall = combos
        zonal_pts = tuple(PitchPoint(x=50.0, y=float(i)) for i in range(n_zonal))
        with pytest.raises(ValidationError):
            DefensiveScheme(
                name="invalid",
                zonal_points=zonal_pts,
                n_man_markers=n_markers,
                wall_size=n_wall,
            )

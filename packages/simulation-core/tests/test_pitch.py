"""Unit tests for the canonical pitch geometry contract."""

import math

import pytest

from restart import ENGINE_VERSION, __version__
from restart.domain import (
    GOAL_HEIGHT_M,
    GOAL_WIDTH_M,
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    is_on_pitch,
)


class TestVersioning:
    def test_engine_version_format(self) -> None:
        # Contract: 'sim/<semver>' - parsed by storage and the UI badge.
        prefix, _, semver = ENGINE_VERSION.partition("/")
        assert prefix == "sim"
        parts = semver.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_package_version_is_semver(self) -> None:
        assert len(__version__.split(".")) == 3


class TestPitchConstants:
    def test_fifa_dimensions(self) -> None:
        assert PITCH_LENGTH_M == 105.0
        assert PITCH_WIDTH_M == 68.0
        assert pytest.approx(7.32) == GOAL_WIDTH_M
        assert pytest.approx(2.44) == GOAL_HEIGHT_M


class TestIsOnPitch:
    def test_center_is_on_pitch(self) -> None:
        assert is_on_pitch(0.0, 0.0)

    @pytest.mark.parametrize(
        ("x", "y"),
        [
            (52.5, 34.0),  # corner flags: boundary lines are in play
            (-52.5, -34.0),
            (52.5, 0.0),  # goal line center
            (0.0, 34.0),  # touchline
        ],
    )
    def test_boundary_inclusive(self, x: float, y: float) -> None:
        assert is_on_pitch(x, y)

    @pytest.mark.parametrize(
        ("x", "y"),
        [
            (52.51, 0.0),
            (-52.51, 0.0),
            (0.0, 34.01),
            (0.0, -34.01),
            (1000.0, 1000.0),
        ],
    )
    def test_outside_bounds(self, x: float, y: float) -> None:
        assert not is_on_pitch(x, y)

    @pytest.mark.parametrize(
        ("x", "y"),
        [
            (math.nan, 0.0),
            (0.0, math.nan),
            (math.inf, 0.0),
            (0.0, -math.inf),
        ],
    )
    def test_non_finite_is_off_pitch(self, x: float, y: float) -> None:
        assert not is_on_pitch(x, y)

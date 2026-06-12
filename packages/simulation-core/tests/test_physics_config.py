"""Configuration model tests: defaults, bounds, immutability, derived values."""

import math

import pytest
from pydantic import ValidationError

from restart.physics import (
    BallConfig,
    DragConfig,
    EnvironmentConfig,
    IntegratorConfig,
    PhysicsConfig,
)


class TestDefaults:
    def test_defaults_match_assumption_registry(self) -> None:
        cfg = PhysicsConfig.default()
        # P-1 FIFA ball, P-2 sea level, P-6 integrator step.
        assert cfg.ball.mass_kg == pytest.approx(0.430)
        assert cfg.ball.radius_m == pytest.approx(0.110)
        assert cfg.environment.air_density_kgm3 == pytest.approx(1.225)
        assert cfg.environment.gravity_ms2 == pytest.approx(9.81)
        assert cfg.integrator.dt_s == pytest.approx(0.005)

    def test_derived_ball_properties(self) -> None:
        ball = BallConfig()
        assert ball.cross_section_m2 == pytest.approx(math.pi * 0.11**2)
        # Thin-shell football: I = (2/3) m r^2 (P-9).
        assert ball.moment_of_inertia == pytest.approx((2 / 3) * 0.430 * 0.11**2)


class TestValidation:
    def test_frozen(self) -> None:
        cfg = BallConfig()
        with pytest.raises(ValidationError):
            cfg.mass_kg = 0.5  # type: ignore[misc]

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            BallConfig(mass_xyz=1.0)  # type: ignore[call-arg]

    @pytest.mark.parametrize("mass", [0.3, 0.5, -1.0])
    def test_implausible_mass_rejected(self, mass: float) -> None:
        with pytest.raises(ValidationError):
            BallConfig(mass_kg=mass)

    def test_drag_crisis_must_reduce_cd(self) -> None:
        with pytest.raises(ValidationError, match="cd_supercritical < cd_subcritical"):
            DragConfig(cd_subcritical=0.25, cd_supercritical=0.45)

    def test_dt_bounds(self) -> None:
        with pytest.raises(ValidationError):
            IntegratorConfig(dt_s=0.1)


class TestAltitude:
    def test_sea_level_is_standard_density(self) -> None:
        env = EnvironmentConfig.at_altitude(0.0)
        assert env.air_density_kgm3 == pytest.approx(1.225)

    def test_mexico_city_thinner_air(self) -> None:
        """WC2026: Estadio Azteca at 2,240 m — materially less drag/Magnus."""
        env = EnvironmentConfig.at_altitude(2240.0)
        assert 0.90 < env.air_density_kgm3 < 1.0

    @pytest.mark.parametrize("alt", [-10.0, 5000.0])
    def test_altitude_bounds(self, alt: float) -> None:
        with pytest.raises(ValueError, match="altitude_m"):
            EnvironmentConfig.at_altitude(alt)

"""Physics configuration models.

Pydantic v2, frozen, range-validated (ADR-001: validation at the boundary,
raw arrays in the hot path). Every default carries its assumption ID from
``docs/simulation-assumptions.md``; bounds reflect physically plausible
ranges, not arbitrary caution.
"""

import math
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DragConfig(_Frozen):
    """Speed-dependent drag coefficient across the drag crisis (P-3).

    C_d(speed) blends smoothly (logistic) from the subcritical to the
    supercritical value around ``v_critical_ms``. Literature anchors:
    Asai et al. 2007; Goff & Carre 2009 (see assumptions registry).
    """

    cd_subcritical: float = Field(default=0.45, gt=0.05, le=1.0)
    cd_supercritical: float = Field(default=0.25, gt=0.05, le=1.0)
    v_critical_ms: float = Field(default=12.0, ge=5.0, le=25.0)
    transition_width_ms: float = Field(default=1.5, ge=0.25, le=10.0)

    @model_validator(mode="after")
    def _crisis_reduces_drag(self) -> Self:
        if self.cd_supercritical >= self.cd_subcritical:
            msg = "drag crisis must reduce C_d: cd_supercritical < cd_subcritical"
            raise ValueError(msg)
        return self


class MagnusConfig(_Frozen):
    """Magnus lift coefficient from spin parameter S = r*|w|/|v| (P-4).

    C_l = S / (a*S + b), S clamped to ``spin_parameter_max``. Empirical-fit
    family per Goff & Carre trajectory analysis; exact constants are
    calibration targets (Phase 3).
    """

    coeff_a: float = Field(default=2.2, gt=0.0, le=10.0)
    coeff_b: float = Field(default=0.7, gt=0.0, le=5.0)
    spin_parameter_max: float = Field(default=0.6, gt=0.0, le=2.0)


class BallConfig(_Frozen):
    """FIFA Law 2 / Quality Programme ball (P-1)."""

    mass_kg: float = Field(default=0.430, ge=0.400, le=0.460)
    radius_m: float = Field(default=0.110, ge=0.105, le=0.115)
    #: Spin decay time constant, exponential (P-5).
    spin_decay_tau_s: float = Field(default=8.0, ge=1.0, le=60.0)
    #: Moment-of-inertia factor beta in I = beta*m*r^2; 2/3 = thin spherical
    #: shell, the standard football idealization (P-9).
    moi_factor: float = Field(default=2.0 / 3.0, ge=0.3, le=0.7)
    drag: DragConfig = Field(default_factory=DragConfig)
    magnus: MagnusConfig = Field(default_factory=MagnusConfig)

    @property
    def cross_section_m2(self) -> float:
        return math.pi * self.radius_m**2

    @property
    def moment_of_inertia(self) -> float:
        return self.moi_factor * self.mass_kg * self.radius_m**2


class EnvironmentConfig(_Frozen):
    """Atmosphere and gravity (P-2)."""

    gravity_ms2: float = Field(default=9.81, ge=9.7, le=9.9)
    air_density_kgm3: float = Field(default=1.225, ge=0.8, le=1.45)

    @classmethod
    def at_altitude(cls, altitude_m: float) -> "EnvironmentConfig":
        """Isothermal barometric approximation (scale height 8,500 m).

        WC2026 relevance: Mexico City (Estadio Azteca, 2,240 m) gives
        rho ~ 0.94 kg/m^3 - about 23% less drag and Magnus than sea level,
        which materially changes deliveries (P-2 note).
        """
        if not 0.0 <= altitude_m <= 4000.0:
            msg = f"altitude_m must be in [0, 4000], got {altitude_m}"
            raise ValueError(msg)
        rho = 1.225 * math.exp(-altitude_m / 8500.0)
        return cls(air_density_kgm3=rho)


class BounceConfig(_Frozen):
    """Ground interaction (P-7, P-8): restitution + Coulomb friction impulse
    with stick/slide branching and spin transfer."""

    restitution: float = Field(default=0.65, ge=0.30, le=0.90)
    #: Sliding friction coefficient during bounce contact.
    friction_mu: float = Field(default=0.40, ge=0.05, le=1.0)
    #: Rolling deceleration coefficient (a = mu_roll * g) once airborne phases end (P-8).
    mu_roll: float = Field(default=0.06, ge=0.01, le=0.30)
    #: Below this post-bounce vertical speed the ball stops bouncing and rolls.
    min_bounce_speed_ms: float = Field(default=0.5, ge=0.05, le=2.0)
    #: Below this total speed a rolling ball is at rest.
    rest_speed_ms: float = Field(default=0.2, ge=0.01, le=1.0)


class IntegratorConfig(_Frozen):
    """Fixed-step RK4 (P-6, ADR-002). Changing dt on persisted results is an
    engine-version-bumping act from Phase 3 onward."""

    dt_s: float = Field(default=0.005, ge=0.0005, le=0.02)
    max_flight_time_s: float = Field(default=15.0, ge=1.0, le=60.0)


class PhysicsConfig(_Frozen):
    """Root physics configuration consumed by simulators."""

    ball: BallConfig = Field(default_factory=BallConfig)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    bounce: BounceConfig = Field(default_factory=BounceConfig)
    integrator: IntegratorConfig = Field(default_factory=IntegratorConfig)

    @classmethod
    def default(cls) -> "PhysicsConfig":
        return cls()

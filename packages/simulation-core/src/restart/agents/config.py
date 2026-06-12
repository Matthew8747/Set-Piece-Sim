"""Agent kinematics configuration.

Frozen pydantic model; all defaults and bounds are calibration knobs for
Phase-3 search (ADR-003 d8). Assumption IDs:
- G-1: accel/speed envelope parameters
- G-3: reaction_jitter_frac models latency noise
"""

from pydantic import Field

from restart.physics.config import _Frozen


class AgentConfig(_Frozen):
    """Configuration for agent kinematics and separation kernels.

    All fields are bounded to physically plausible ranges; defaults match the
    ADR-003 design point. Phase-3 calibration may tune these via config, not
    code.
    """

    #: Agent simulation tick size (s). Must match the engine outer-loop dt.
    dt_s: float = Field(default=0.02, ge=0.005, le=0.05)

    #: Maximum heading-change rate scale (rad/s at full agility, slow speed).
    #: Turn rate = dt * turn_rate_base * (0.25 + 0.75*agility) * speed_ref/(v+speed_ref).
    #: (G-1: turn-rate envelope)
    turn_rate_base_rads: float = Field(default=8.0, ge=1.0, le=20.0)

    #: Reference speed for the speed-dependent turn-rate taper (m/s). (G-1)
    turn_speed_ref_ms: float = Field(default=4.0, ge=1.0, le=10.0)

    #: Agent is considered to have arrived when within this radius of its
    #: target (m); velocity zeroed on arrival (arrive-and-hold). (G-1)
    arrival_radius_m: float = Field(default=0.3, ge=0.05, le=1.0)

    #: Soft-disc separation enforcement radius (m). Two agents overlap when
    #: centre distance < 2*radius. (G-7: soft-disc separation)
    separation_radius_m: float = Field(default=0.4, ge=0.1, le=1.0)

    #: Fractional jitter applied to reaction time draws (G-3). Each agent's
    #: effective ready_time = reaction_time_s * U(1 - frac, 1 + frac).
    reaction_jitter_frac: float = Field(default=0.15, ge=0.0, le=0.5)

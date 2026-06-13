"""Engine configuration: every behavioral constant of the set-piece engine.

All fields are Phase-3 calibration knobs unless marked [fixed]. Registered as
G-assumptions in docs/simulation-assumptions.md.
"""

from pydantic import BaseModel, ConfigDict, Field


class EngineConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # --- timing [fixed by ADR-003 d3] ---
    agent_dt_s: float = Field(default=0.02, ge=0.005, le=0.05)
    # Runs need ~1.2 s of development: accel-limited agents cover <1 m in
    # 0.5 s, which made arriving runners universally late to contests.
    prekick_lead_s: float = Field(default=1.5, ge=0.2, le=3.0)
    trigger_kick_approach_s: float = Field(default=-1.2, ge=-2.5, le=-0.1)

    # --- delivery execution (G-11) ---
    # Elevation is solved from the drag-free range equation with a carry
    # correction (drag shortens range): sin(2*theta) = d*g/(speed*carry)^2.
    carry_factor: float = Field(default=0.82, ge=0.5, le=1.0)
    elev_floor_cross_deg: float = Field(default=8.0, ge=2.0, le=20.0)
    elev_floor_driven_deg: float = Field(default=4.0, ge=1.0, le=15.0)
    elev_floor_floated_deg: float = Field(default=14.0, ge=5.0, le=30.0)
    elev_floor_short_deg: float = Field(default=2.0, ge=0.0, le=10.0)
    elev_max_deg: float = Field(default=35.0, ge=15.0, le=45.0)
    dir_noise_base_rad: float = Field(default=0.06, ge=0.0, le=0.3)
    speed_noise_frac: float = Field(default=0.06, ge=0.0, le=0.3)
    # Takers pre-aim against the curl so spin brings the ball back to target:
    # heading shift = -spin_sign * this * spin_rps (radians per rev/s).
    curl_compensation_rad_per_rps: float = Field(default=0.014, ge=0.0, le=0.05)

    # --- contest resolution (G-6) ---
    # Window after the earliest feasible arrival within which later arrivals
    # still join the same aerial contest. 0.20 s ~ one stride: static zonal
    # defenders are otherwise unbeatable by arriving runners. [knob]
    contest_window_s: float = Field(default=0.20, ge=0.01, le=0.5)
    w_reach: float = Field(default=1.5, ge=0.0, le=10.0)  # per meter of reach margin
    w_time: float = Field(default=2.0, ge=0.0, le=10.0)  # per second of arrival slack
    w_strength: float = Field(default=0.8, ge=0.0, le=5.0)
    w_heading: float = Field(default=0.8, ge=0.0, le=5.0)
    gk_claim_bonus: float = Field(default=0.6, ge=0.0, le=5.0)
    gumbel_scale: float = Field(default=0.5, ge=0.01, le=5.0)

    # --- contact resolution (P-12 cap, G-12 aim model) ---
    header_speed_base_ms: float = Field(default=8.0, ge=2.0, le=15.0)
    header_dir_sigma_rad: float = Field(default=0.10, ge=0.01, le=0.5)
    shot_aim_y_max_m: float = Field(default=3.0, ge=0.5, le=3.6)
    shot_aim_z_min_m: float = Field(default=0.3, ge=0.0, le=1.0)
    shot_aim_z_max_m: float = Field(default=2.2, ge=1.0, le=2.44)
    clear_speed_base_ms: float = Field(default=12.0, ge=5.0, le=20.0)
    clear_speed_strength_ms: float = Field(default=8.0, ge=0.0, le=15.0)
    clear_elev_deg: float = Field(default=25.0, ge=5.0, le=60.0)

    # --- goalkeeper save model (G-9): logit-linear in shot features ---
    save_c0: float = Field(default=0.8, ge=-5.0, le=5.0)
    save_c_speed: float = Field(default=-0.8, ge=-5.0, le=0.0)  # per +10 m/s over 20
    save_c_placement: float = Field(default=-0.9, ge=-5.0, le=0.0)  # per meter from GK
    save_c_distance: float = Field(default=0.06, ge=0.0, le=1.0)  # per meter of range

    # --- second ball (G-10) ---
    second_ball_radius_m: float = Field(default=4.0, ge=1.0, le=10.0)

"""Vectorized batch flight engine - the Monte Carlo throughput path.

Two implementations, one contract:

* **Production path** (default force model): the fused Numba kernel in
  ``_kernels.py`` - adopted after the NumPy path measured 6.8 s for 10k
  flights against the 1 s budget (ADR-001 addendum).
* **Reference path** (``_simulate_flights_numpy``): the readable NumPy
  lockstep implementation. It defines the semantics, serves custom force
  models (kernel only fuses the default gravity+drag+Magnus system), and the
  test suite enforces kernel<->reference equivalence to 1e-9.

Scope (Phase 1): launch -> first ground contact (or time cap). Bounce chains
and full event logs in batch mode arrive with the Monte Carlo layer (Phase 3).
Use ``TrajectorySimulator`` for event-complete single trajectories.
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from restart.domain.vectors import FloatArray
from restart.physics import _kernels
from restart.physics.config import PhysicsConfig
from restart.physics.forces import default_force_system
from restart.physics.integrator import make_derivative, rk4_step
from restart.simulation.interfaces import ForceModel

BoolArray = npt.NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class FlightBatchResult:
    """Per-sim landing summary; arrays are read-only, indexed by sim."""

    landing_time_s: FloatArray  # (n,) NaN where not landed
    landing_position: FloatArray  # (n, 3) NaN where not landed
    landing_velocity: FloatArray  # (n, 3) NaN where not landed
    landing_spin: FloatArray  # (n, 3) NaN where not landed
    apex_height_m: FloatArray  # (n,) running max of z (valid for all sims)
    landed: BoolArray  # (n,) False if max_flight_time hit first

    @property
    def n_sims(self) -> int:
        return int(self.landed.shape[0])


def _validate_initial(initial: FloatArray) -> FloatArray:
    if initial.ndim != 2 or initial.shape[1] != 9:
        msg = f"initial must have shape (n, 9), got {initial.shape}"
        raise ValueError(msg)
    return np.ascontiguousarray(initial, dtype=np.float64)


def _package(
    landing_y: FloatArray, landing_t: FloatArray, apex: FloatArray, landed: BoolArray
) -> FlightBatchResult:
    result = FlightBatchResult(
        landing_time_s=landing_t,
        landing_position=landing_y[:, 0:3],
        landing_velocity=landing_y[:, 3:6],
        landing_spin=landing_y[:, 6:9],
        apex_height_m=apex,
        landed=landed,
    )
    for arr in (landing_y, landing_t, apex, landed):
        arr.setflags(write=False)
    return result


def simulate_flights(
    initial: FloatArray,
    config: PhysicsConfig | None = None,
    force: ForceModel | None = None,
) -> FlightBatchResult:
    """Fly a batch of packed states ``(n, 9)`` to first ground contact.

    Deterministic: identical inputs produce bit-identical outputs (a single
    production code path - the JIT kernel - guarantees this for the default
    force model; passing a custom ``force`` routes to the NumPy reference).
    """
    cfg = config if config is not None else PhysicsConfig.default()
    y0 = _validate_initial(initial)

    if force is not None:
        return _simulate_flights_numpy(y0, cfg, force)

    ball, env = cfg.ball, cfg.environment
    k_aero = 0.5 * env.air_density_kgm3 * ball.cross_section_m2 / ball.mass_kg
    n_steps = int(np.ceil(cfg.integrator.max_flight_time_s / cfg.integrator.dt_s))

    landing_y, landing_t, apex, landed = _kernels.flight_batch(
        y0,
        cfg.integrator.dt_s,
        n_steps,
        ball.radius_m,
        env.gravity_ms2,
        k_aero,
        ball.drag.cd_subcritical,
        ball.drag.cd_supercritical,
        ball.drag.v_critical_ms,
        ball.drag.transition_width_ms,
        ball.radius_m,
        ball.magnus.coeff_a,
        ball.magnus.coeff_b,
        ball.magnus.spin_parameter_max,
        ball.spin_decay_tau_s,
    )
    return _package(landing_y, landing_t, apex, landed)


def _simulate_flights_numpy(
    y0: FloatArray, cfg: PhysicsConfig, force: ForceModel | None = None
) -> FlightBatchResult:
    """Readable NumPy lockstep reference (semantics oracle for the kernel)."""
    f = force if force is not None else default_force_system(cfg.ball, cfg.environment)
    derivative = make_derivative(f, cfg.ball.spin_decay_tau_s)
    dt = cfg.integrator.dt_s
    ground_z = cfg.ball.radius_m
    n = y0.shape[0]

    y = y0.copy()
    active = np.ones(n, dtype=np.bool_)
    landing_y = np.full((n, 9), np.nan)
    landing_t = np.full(n, np.nan)
    apex = y[:, 2].copy()

    t = 0.0
    n_steps = int(np.ceil(cfg.integrator.max_flight_time_s / dt))
    for _ in range(n_steps):
        if not active.any():
            break
        y_new = rk4_step(y, dt, derivative)
        t_new = t + dt

        crossed = active & (y[:, 2] >= ground_z) & (y_new[:, 2] < ground_z) & (y_new[:, 5] < 0.0)
        if crossed.any():
            dz = y[crossed, 2] - y_new[crossed, 2]
            frac = (y[crossed, 2] - ground_z) / dz
            y_land = y[crossed] + frac[:, np.newaxis] * (y_new[crossed] - y[crossed])
            y_land[:, 2] = ground_z
            landing_y[crossed] = y_land
            landing_t[crossed] = t + frac * dt
            active[crossed] = False

        apex = np.where(active, np.maximum(apex, y_new[:, 2]), apex)
        y = y_new
        t = t_new

    return _package(landing_y, landing_t, apex, ~active)

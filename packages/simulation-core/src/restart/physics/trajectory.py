"""Single-trajectory simulator with event extraction.

Plays out one ball from launch to termination (goal, out of play, rest, or
time cap), recording dense samples for replay and typed events for analytics.
This is the *analysis/replay* path; the Monte Carlo throughput path is the
batch engine (``restart.physics.batch``).

Phase structure per flight arc:

    FLIGHT --(ground contact)--> bounce? --> FLIGHT ...
           --(bounce too weak)--> ROLLING --(slow)--> REST

Crossing events (goal mouth, boundaries) terminate in both phases. All
crossings are refined by linear interpolation within the step (P-14); within
a single step the earliest crossing wins.
"""

from dataclasses import dataclass

import numpy as np

from restart.domain import pitch
from restart.domain.vectors import FloatArray
from restart.physics.bounce import bounce, energy_retained
from restart.physics.config import PhysicsConfig
from restart.physics.forces import default_force_system
from restart.physics.integrator import make_derivative, rk4_step
from restart.physics.state import BallState
from restart.simulation.events import (
    ApexEvent,
    BounceEvent,
    GoalEvent,
    LaunchEvent,
    OutOfPlayEvent,
    RestEvent,
    SimEvent,
    TerminationReason,
)
from restart.simulation.interfaces import ForceModel


@dataclass(frozen=True, slots=True)
class TrajectorySamples:
    """Dense state samples on the integrator grid (read-only arrays)."""

    times_s: FloatArray  # (n,)
    positions: FloatArray  # (n, 3)
    velocities: FloatArray  # (n, 3)
    spins: FloatArray  # (n, 3)

    def __len__(self) -> int:
        return int(self.times_s.shape[0])


@dataclass(frozen=True, slots=True)
class Trajectory:
    samples: TrajectorySamples
    events: tuple[SimEvent, ...]
    termination: TerminationReason
    final_state: BallState

    @property
    def goal_scored(self) -> bool:
        return self.termination is TerminationReason.GOAL

    @property
    def apex_height_m(self) -> float:
        return float(np.max(self.samples.positions[:, 2]))

    @property
    def flight_time_s(self) -> float:
        return self.final_state.time_s - float(self.samples.times_s[0])


def _interp(a: FloatArray, b: FloatArray, frac: float) -> FloatArray:
    return a + frac * (b - a)


class TrajectorySimulator:
    """Event-extracting ball simulator (implements ``BallSimulator``)."""

    def __init__(self, config: PhysicsConfig | None = None, force: ForceModel | None = None):
        self._cfg = config if config is not None else PhysicsConfig.default()
        self._force = (
            force
            if force is not None
            else default_force_system(self._cfg.ball, self._cfg.environment)
        )
        self._derivative = make_derivative(self._force, self._cfg.ball.spin_decay_tau_s)

    @property
    def config(self) -> PhysicsConfig:
        return self._cfg

    def simulate(self, initial: BallState) -> Trajectory:
        cfg = self._cfg
        dt = cfg.integrator.dt_s
        ground_z = cfg.ball.radius_m

        y = initial.to_vector()
        t = initial.time_s
        rolling = False

        times = [t]
        states = [y.copy()]
        events: list[SimEvent] = [
            LaunchEvent(
                time_s=t,
                position=initial.position,
                speed_ms=initial.speed_ms,
                spin_rps=initial.spin_rps,
            )
        ]
        termination: TerminationReason | None = None
        final_y, final_t = y, t

        max_t = initial.time_s + cfg.integrator.max_flight_time_s
        while termination is None and t < max_t:
            y_new = self._step_rolling(y, dt) if rolling else rk4_step(y, dt, self._derivative)
            t_new = t + dt

            # --- terminal crossings (earliest within the step wins) ---------
            crossing = self._earliest_crossing(y, y_new, t, dt)
            if crossing is not None:
                frac, event, reason = crossing
                y_cross = _interp(y, y_new, frac)
                t_cross = t + frac * dt
                events.append(event)
                times.append(t_cross)
                states.append(y_cross)
                final_y, final_t = y_cross, t_cross
                termination = reason
                break

            if not rolling:
                # --- apex (non-terminal, record and continue) ----------------
                if y[5] > 0.0 >= y_new[5]:
                    frac = y[5] / (y[5] - y_new[5])
                    y_apex = _interp(y, y_new, frac)
                    events.append(ApexEvent(time_s=t + frac * dt, position=y_apex[0:3].copy()))

                # --- ground contact ------------------------------------------
                if y[2] >= ground_z > y_new[2] and y_new[5] < 0.0:
                    frac = (y[2] - ground_z) / (y[2] - y_new[2])
                    y_land = _interp(y, y_new, frac)
                    y_land[2] = ground_z
                    t_land = t + frac * dt
                    v_in, w_in = y_land[3:6].copy(), y_land[6:9].copy()

                    if cfg.bounce.restitution * (-v_in[2]) < cfg.bounce.min_bounce_speed_ms:
                        # Too weak to bounce: transition to rolling.
                        y_land[5] = 0.0
                        rolling = True
                    else:
                        v_out, w_out = bounce(v_in, w_in, cfg.bounce, cfg.ball)
                        y_land[3:6] = v_out
                        y_land[6:9] = w_out
                        events.append(
                            BounceEvent(
                                time_s=t_land,
                                position=y_land[0:3].copy(),
                                impact_speed_ms=float(np.linalg.norm(v_in)),
                                energy_retained=energy_retained(
                                    v_in, w_in, y_land[3:6], y_land[6:9], cfg.ball
                                ),
                            )
                        )
                    times.append(t_land)
                    states.append(y_land.copy())
                    y, t = y_land, t_land
                    final_y, final_t = y, t
                    continue
            elif float(np.linalg.norm(y_new[3:5])) < cfg.bounce.rest_speed_ms:
                # --- rolling rest ---------------------------------------------
                y_new[3:6] = 0.0
                events.append(RestEvent(time_s=t_new, position=y_new[0:3].copy()))
                times.append(t_new)
                states.append(y_new.copy())
                final_y, final_t = y_new, t_new
                termination = TerminationReason.REST
                break

            times.append(t_new)
            states.append(y_new.copy())
            y, t = y_new, t_new
            final_y, final_t = y, t

        if termination is None:
            termination = TerminationReason.MAX_TIME

        stacked = np.vstack(states)
        samples = TrajectorySamples(
            times_s=_readonly(np.asarray(times, dtype=np.float64)),
            positions=_readonly(stacked[:, 0:3]),
            velocities=_readonly(stacked[:, 3:6]),
            spins=_readonly(stacked[:, 6:9]),
        )
        return Trajectory(
            samples=samples,
            events=tuple(events),
            termination=termination,
            final_state=BallState.from_vector(final_y, time_s=final_t),
        )

    def _step_rolling(self, y: FloatArray, dt: float) -> FloatArray:
        """Rolling regime (P-8): constant deceleration mu_roll * g along -v,
        pinned to the ground plane; spin follows the exponential decay."""
        cfg = self._cfg
        out = y.copy()
        v_h = y[3:5]
        speed = float(np.linalg.norm(v_h))
        if speed > 0.0:
            decel = cfg.bounce.mu_roll * cfg.environment.gravity_ms2
            new_speed = max(0.0, speed - decel * dt)
            out[3:5] = v_h * (new_speed / speed)
        out[5] = 0.0
        out[0:2] = y[0:2] + 0.5 * (y[3:5] + out[3:5]) * dt  # trapezoidal position
        out[2] = cfg.ball.radius_m
        out[6:9] = y[6:9] * (1.0 - dt / cfg.ball.spin_decay_tau_s)
        return out

    def _earliest_crossing(
        self, y: FloatArray, y_new: FloatArray, t: float, dt: float
    ) -> tuple[float, SimEvent, TerminationReason] | None:
        """Goal-line and touchline plane crossings within the step, if any."""
        candidates: list[tuple[float, SimEvent, TerminationReason]] = []

        for sign in (1.0, -1.0):
            gx = sign * pitch.HALF_LENGTH_M
            if (y[0] - gx) * (y_new[0] - gx) < 0.0:
                frac = float((gx - y[0]) / (y_new[0] - y[0]))
                p = _interp(y, y_new, frac)[0:3]
                t_cross = t + frac * dt
                if pitch.is_in_goal_mouth(float(p[1]), float(p[2])):
                    event: SimEvent = GoalEvent(
                        time_s=t_cross,
                        position=p.copy(),
                        entry_y_m=float(p[1]),
                        entry_z_m=float(p[2]),
                    )
                    candidates.append((frac, event, TerminationReason.GOAL))
                else:
                    boundary = "goal_line+x" if sign > 0 else "goal_line-x"
                    candidates.append(
                        (
                            frac,
                            OutOfPlayEvent(time_s=t_cross, position=p.copy(), boundary=boundary),
                            TerminationReason.OUT_OF_PLAY,
                        )
                    )

        for sign in (1.0, -1.0):
            ty = sign * pitch.HALF_WIDTH_M
            if (y[1] - ty) * (y_new[1] - ty) < 0.0:
                frac = float((ty - y[1]) / (y_new[1] - y[1]))
                p = _interp(y, y_new, frac)[0:3]
                boundary = "touchline+y" if sign > 0 else "touchline-y"
                candidates.append(
                    (
                        frac,
                        OutOfPlayEvent(time_s=t + frac * dt, position=p.copy(), boundary=boundary),
                        TerminationReason.OUT_OF_PLAY,
                    )
                )

        if not candidates:
            return None
        return min(candidates, key=lambda c: c[0])


def _readonly(a: FloatArray) -> FloatArray:
    a.setflags(write=False)
    return a

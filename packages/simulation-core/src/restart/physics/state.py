"""Ball state: the 9-dimensional kinematic state [position, velocity, spin].

``BallState`` is the boundary type (immutable, validated shape); the packed
``(..., 9)`` float64 vector is the hot-path representation the integrator
actually steps (ADR-002). Conversion is explicit and cheap.
"""

from dataclasses import dataclass, field

import numpy as np

from restart.domain.vectors import FloatArray


def _readonly_vec3(v: FloatArray, name: str) -> FloatArray:
    arr = np.asarray(v, dtype=np.float64).copy()
    if arr.shape != (3,):
        msg = f"{name} must have shape (3,), got {arr.shape}"
        raise ValueError(msg)
    if not np.all(np.isfinite(arr)):
        msg = f"{name} must be finite, got {arr}"
        raise ValueError(msg)
    arr.setflags(write=False)
    return arr


@dataclass(frozen=True, slots=True)
class BallState:
    """Immutable ball snapshot in the canonical frame (meters, m/s, rad/s).

    Arrays are defensively copied and marked read-only at construction, so a
    BallState cannot be mutated through aliased references either.
    """

    position: FloatArray
    velocity: FloatArray
    spin: FloatArray = field(default_factory=lambda: np.zeros(3))
    time_s: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "position", _readonly_vec3(self.position, "position"))
        object.__setattr__(self, "velocity", _readonly_vec3(self.velocity, "velocity"))
        object.__setattr__(self, "spin", _readonly_vec3(self.spin, "spin"))
        if not np.isfinite(self.time_s) or self.time_s < 0.0:
            msg = f"time_s must be finite and >= 0, got {self.time_s}"
            raise ValueError(msg)

    def to_vector(self) -> FloatArray:
        """Pack into the integrator's state vector ``(9,)`` (writable copy)."""
        return np.concatenate([self.position, self.velocity, self.spin])

    @classmethod
    def from_vector(cls, y: FloatArray, time_s: float = 0.0) -> "BallState":
        """Unpack an integrator state vector ``(9,)``."""
        if y.shape != (9,):
            msg = f"state vector must have shape (9,), got {y.shape}"
            raise ValueError(msg)
        return cls(position=y[0:3], velocity=y[3:6], spin=y[6:9], time_s=time_s)

    @property
    def speed_ms(self) -> float:
        return float(np.linalg.norm(self.velocity))

    @property
    def spin_rps(self) -> float:
        """Spin magnitude in revolutions per second (display convenience)."""
        return float(np.linalg.norm(self.spin)) / (2.0 * np.pi)


def pack_states(positions: FloatArray, velocities: FloatArray, spins: FloatArray) -> FloatArray:
    """Pack batch arrays ``(n, 3)`` x3 into the batch state tensor ``(n, 9)``."""
    if not (positions.shape == velocities.shape == spins.shape) or positions.shape[-1] != 3:
        msg = (
            "positions, velocities, spins must share shape (n, 3); got "
            f"{positions.shape}, {velocities.shape}, {spins.shape}"
        )
        raise ValueError(msg)
    return np.concatenate(
        [
            np.asarray(positions, dtype=np.float64),
            np.asarray(velocities, dtype=np.float64),
            np.asarray(spins, dtype=np.float64),
        ],
        axis=-1,
    )

"""Protocols between simulation layers.

Deliberately minimal (YAGNI): each protocol exists because a second
implementation or a consumer in another layer is already designed —
ForceModel (per-force composition now, wind/altitude variants later),
BallSimulator (TrajectorySimulator now, agent-coupled simulator in Phase 2,
Monte Carlo batch wrapper in Phase 3).
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from restart.domain.vectors import FloatArray

if TYPE_CHECKING:
    from restart.physics.state import BallState
    from restart.physics.trajectory import Trajectory


@runtime_checkable
class ForceModel(Protocol):
    """A force expressed as acceleration on the ball.

    Kernel contract (ADR-001 Numba-readiness): broadcast-polymorphic pure
    function of arrays — position/velocity/spin shaped ``(..., 3)``, returning
    acceleration ``(..., 3)``. No mutation, no I/O, no Python-object state in
    the call path.
    """

    @property
    def name(self) -> str: ...

    def acceleration(
        self, position: FloatArray, velocity: FloatArray, spin: FloatArray
    ) -> FloatArray: ...


class BallSimulator(Protocol):
    """Anything that can play out a ball from an initial state."""

    def simulate(self, initial: "BallState") -> "Trajectory": ...

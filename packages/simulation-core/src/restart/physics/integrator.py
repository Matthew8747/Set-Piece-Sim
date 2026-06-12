"""Fixed-step RK4 integration of the ball state (ADR-002, P-6).

State vector layout (last axis, length 9):

    y = [px py pz | vx vy vz | wx wy wz]

The derivative is autonomous (no explicit time dependence):

    dy/dt = [v | a(r, v, w) | -w / tau]

Spin decays exponentially inside the state vector (P-5) rather than as a
post-step correction, so all integrators/oracles see the same ODE.

Kernels are broadcast-polymorphic: a single state ``(9,)`` and a batch
``(n, 9)`` take the identical code path.
"""

from collections.abc import Callable

from restart.domain.vectors import FloatArray
from restart.simulation.interfaces import ForceModel

Derivative = Callable[[FloatArray], FloatArray]


def make_derivative(force: ForceModel, spin_decay_tau_s: float) -> Derivative:
    """Build dy/dt from a force model (acceleration) and spin decay."""

    def derivative(y: FloatArray) -> FloatArray:
        out = y.copy()  # same shape/dtype; every slot overwritten below
        r = y[..., 0:3]
        v = y[..., 3:6]
        w = y[..., 6:9]
        out[..., 0:3] = v
        out[..., 3:6] = force.acceleration(r, v, w)
        out[..., 6:9] = -w / spin_decay_tau_s
        return out

    return derivative


def rk4_step(y: FloatArray, dt: float, derivative: Derivative) -> FloatArray:
    """One classical Runge-Kutta 4 step. Pure: returns a new array."""
    k1 = derivative(y)
    k2 = derivative(y + (0.5 * dt) * k1)
    k3 = derivative(y + (0.5 * dt) * k2)
    k4 = derivative(y + dt * k3)
    return y + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

"""Typed 3-vector utilities over NumPy.

All physics code operates on float64 arrays whose **last axis is the spatial
axis** (length 3) or the packed state axis (length 9). Every helper here is
broadcast-polymorphic: it accepts a single vector ``(3,)`` or a batch
``(n, 3)`` identically (ADR-002, decision 2).

Kernel discipline (ADR-001, Numba-readiness): pure functions, float64
in/float64 out, no Python objects in signatures.
"""

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]

#: Guard against division by zero when normalizing; vectors shorter than this
#: are treated as zero (their "unit vector" is the zero vector - see `unit`).
_EPS: float = 1e-12


def vec3(x: float, y: float, z: float) -> FloatArray:
    """Construct a single float64 3-vector."""
    return np.array([x, y, z], dtype=np.float64)


def norm(v: FloatArray) -> FloatArray:
    """Euclidean norm along the last axis. ``(..., 3) -> (...)``."""
    result: FloatArray = np.sqrt(np.sum(v * v, axis=-1))
    return result


def unit(v: FloatArray) -> FloatArray:
    """Unit vector along the last axis; the zero vector maps to itself.

    The zero-maps-to-zero convention is load-bearing: Magnus force uses
    ``unit(spin x velocity)``, which must vanish smoothly when spin is zero or
    parallel to velocity rather than raise or produce NaN.
    """
    n = np.sqrt(np.sum(v * v, axis=-1, keepdims=True))
    result: FloatArray = v / np.maximum(n, _EPS)
    return result


def cross(a: FloatArray, b: FloatArray) -> FloatArray:
    """Cross product along the last axis.

    Hand-expanded rather than ``np.cross``: numpy's implementation routes
    through moveaxis machinery that costs ~100x on small arrays, and this
    sits inside the per-step force evaluation (profiled: ~25% of engine
    time before the rewrite).
    """
    shape = np.broadcast_shapes(a.shape, b.shape)
    result: FloatArray = np.empty(shape, dtype=np.float64)
    result[..., 0] = a[..., 1] * b[..., 2] - a[..., 2] * b[..., 1]
    result[..., 1] = a[..., 2] * b[..., 0] - a[..., 0] * b[..., 2]
    result[..., 2] = a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]
    return result


def dot(a: FloatArray, b: FloatArray) -> FloatArray:
    """Dot product along the last axis. ``(..., 3) -> (...)``."""
    result: FloatArray = np.sum(a * b, axis=-1)
    return result


def horizontal(v: FloatArray) -> FloatArray:
    """Project onto the pitch plane (zero the z component), preserving shape."""
    out = v.copy()
    out[..., 2] = 0.0
    return out

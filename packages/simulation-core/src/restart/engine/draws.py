"""Externalized per-sim RNG draw plan (ADR-011, Phase 10).

Numba's in-kernel RNG cannot reproduce NumPy's Philox stream bit-for-bit, so a
stochastic Numba kernel can only match the NumPy reference engine to <=1e-9 if
both consume the *same* draws. This module is that seam: every stochastic draw a
single set-piece simulation needs is generated here, up front, into a
``SimDraws`` struct that the engine and the kernel both read instead of calling
``rng`` directly.

Design (ADR-011 decision 2): each draw *category* is an independent
``SeedSequence`` sub-stream, each with a fixed budget. Independence means
over-provisioning one category (notably the variable-count contest Gumbels,
budgeted to the max ``na + nd`` potential contestants) never shifts another
category's draws - the property a single lazy stream lacks, and the reason the
old single-stream draw order is replaced (a one-time canonical re-baseline;
model identical, ``ENGINE_VERSION`` unchanged).

Draws are raw, unit-scale variates (standard normal / U(0,1) / U(-1,1) /
standard Gumbel); the engine and kernel apply the program+config scaling. So
``SimDraws`` is a pure function of ``(seed, n_attackers, n_defenders)`` -
scenario- and config-independent - which keeps determinism byte-identical across
batch sizes (the carried hard constraint).
"""

from __future__ import annotations

import dataclasses

import numpy as np

from restart.domain.vectors import FloatArray

# Category sub-stream indices (order is the public draw-plan contract).
_DELIVERY, _JITTER, _CONTEST, _SHOT, _SECOND = range(5)
_N_CATEGORIES = 5


@dataclasses.dataclass(frozen=True, slots=True)
class SimDraws:
    """Raw unit-scale RNG draws for one simulation (ADR-011).

    Arrays are float64, C-contiguous, read-only. Scaling is applied by the
    consumer (engine/kernel), not here.

    delivery     : (2,)      standard normal - [direction error, speed multiplier]
    jitter       : (na+nd,)  U(-1, 1)        - reaction jitter, attackers then defenders
    contest      : (na+nd,)  standard Gumbel - one slot per potential contestant by index
    shot_aim_y   : scalar    U(-1, 1)        - lateral aim
    shot_aim_z   : scalar    U(0, 1)         - vertical aim
    shot_perturb : (2,)      standard normal - header/volley direction perturbation
    shot_final   : scalar    U(0, 1)         - xG Bernoulli (xG path) OR GK save (placeholder path)
    second_ball  : scalar    U(0, 1)         - near-tie jitter for the loose-ball race
    """

    delivery: FloatArray
    jitter: FloatArray
    contest: FloatArray
    shot_aim_y: float
    shot_aim_z: float
    shot_perturb: FloatArray
    shot_final: float
    second_ball: float


def _ro(arr: FloatArray) -> FloatArray:
    arr.setflags(write=False)
    return arr


def _gen(child: np.random.SeedSequence) -> np.random.Generator:
    """Philox generator from a spawned sub-stream (matches simulation/rng.py)."""
    return np.random.Generator(np.random.Philox(child))


def draw_sim(seed: int, n_attackers: int, n_defenders: int) -> SimDraws:
    """Draw all per-sim randomness for one simulation (ADR-011).

    Deterministic in ``(seed, n_attackers, n_defenders)``; category sub-streams
    are independent (see module docstring). ``seed`` is the per-sim seed
    (e.g. from ``montecarlo.runner.sim_seeds``).
    """
    if n_attackers <= 0 or n_defenders <= 0:
        msg = f"n_attackers and n_defenders must be > 0, got {n_attackers}, {n_defenders}"
        raise ValueError(msg)

    n = n_attackers + n_defenders
    children = np.random.SeedSequence(seed).spawn(_N_CATEGORIES)
    g_del = _gen(children[_DELIVERY])
    g_jit = _gen(children[_JITTER])
    g_con = _gen(children[_CONTEST])
    g_shot = _gen(children[_SHOT])
    g_sec = _gen(children[_SECOND])

    delivery = g_del.standard_normal(2)
    jitter = g_jit.uniform(-1.0, 1.0, n)
    contest = g_con.gumbel(0.0, 1.0, n)
    # Fixed draw order within the shot sub-stream is part of the contract.
    shot_aim_y = float(g_shot.uniform(-1.0, 1.0))
    shot_aim_z = float(g_shot.uniform(0.0, 1.0))
    shot_perturb = g_shot.standard_normal(2)
    shot_final = float(g_shot.uniform(0.0, 1.0))
    second_ball = float(g_sec.uniform(0.0, 1.0))

    return SimDraws(
        delivery=_ro(np.ascontiguousarray(delivery, dtype=np.float64)),
        jitter=_ro(np.ascontiguousarray(jitter, dtype=np.float64)),
        contest=_ro(np.ascontiguousarray(contest, dtype=np.float64)),
        shot_aim_y=shot_aim_y,
        shot_aim_z=shot_aim_z,
        shot_perturb=_ro(np.ascontiguousarray(shot_perturb, dtype=np.float64)),
        shot_final=shot_final,
        second_ball=second_ball,
    )

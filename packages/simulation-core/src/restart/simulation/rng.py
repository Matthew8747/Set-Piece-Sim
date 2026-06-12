"""Deterministic, parallel-safe RNG streams (ADR-003 d9).

Uses NumPy's Philox bit-generator with SeedSequence spawning to produce
independent child streams from a single root seed. Design guarantees:

- Same (root_seed, stream) pair always produces identical draw sequences.
- Different stream indices produce statistically independent sequences
  (Philox counter-based PRNG; SeedSequence ensures orthogonal initialisation).
- Parallel safety: stream indices map to non-overlapping counter blocks.

Typical usage in the engine::

    rng = spawn_rng(root_seed=42, stream=sim_index)
    # All stochastic draws in the sim consume from this single generator
    # in a fixed order: delivery noise → reaction jitter → contest Gumbel → …
"""

import numpy as np


def spawn_rng(root_seed: int, stream: int) -> np.random.Generator:
    """Create a reproducible child RNG stream (ADR-003 d9).

    Parameters
    ----------
    root_seed : int  Master seed for the simulation study (>= 0).
    stream    : int  Per-simulation stream index (>= 0); different values
                     produce statistically independent generators.

    Returns
    -------
    numpy.random.Generator backed by Philox with a SeedSequence-derived key.

    Raises
    ------
    ValueError  if root_seed or stream is negative.
    """
    if root_seed < 0:
        msg = f"root_seed must be >= 0, got {root_seed}"
        raise ValueError(msg)
    if stream < 0:
        msg = f"stream must be >= 0, got {stream}"
        raise ValueError(msg)
    seq = np.random.SeedSequence(root_seed, spawn_key=(stream,))
    return np.random.Generator(np.random.Philox(seq))


def spawn_rngs(root_seed: int, n: int) -> list[np.random.Generator]:
    """Spawn *n* independent child streams from a single root seed (ADR-003 d9).

    Parameters
    ----------
    root_seed : int  Master seed.
    n         : int  Number of streams to create (>= 0).

    Returns
    -------
    list of numpy.random.Generator, one per stream index 0 … n-1.

    Raises
    ------
    ValueError  if root_seed < 0 or n < 0.
    """
    if root_seed < 0:
        msg = f"root_seed must be >= 0, got {root_seed}"
        raise ValueError(msg)
    if n < 0:
        msg = f"n must be >= 0, got {n}"
        raise ValueError(msg)
    return [spawn_rng(root_seed, i) for i in range(n)]

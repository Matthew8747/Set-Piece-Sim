"""Canonical scenario hashing for idempotency (ADR-007 d3, doc 02 4.1/6).

The scenario hash is the SHA-256 of the spec serialized as canonical JSON (keys
sorted, no insignificant whitespace), so logically-identical specs hash equally
regardless of key order. The idempotency key folds the hash with the run's seed
and the engine version: a duplicate key returns the existing run rather than
recomputing, which also guarantees the determinism contract (same inputs ⇒ same
surfaced result).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical(spec: dict[str, Any]) -> str:
    return json.dumps(spec, sort_keys=True, separators=(",", ":"))


def scenario_hash(spec: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(spec).encode("utf-8")).hexdigest()


def idempotency_key(spec: dict[str, Any], seed: int, engine_version: str) -> str:
    payload = f"{scenario_hash(spec)}|{seed}|{engine_version}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

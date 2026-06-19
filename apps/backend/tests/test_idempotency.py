"""Canonical scenario hash + idempotency key (ADR-007 d3, doc 02 4.1/6)."""

from restart_api.hashing import idempotency_key, scenario_hash


def test_scenario_hash_is_canonical_and_stable() -> None:
    a = scenario_hash({"routine_id": "r", "scheme_id": "s", "att": "England"})
    b = scenario_hash({"att": "England", "scheme_id": "s", "routine_id": "r"})
    assert a == b  # key order does not matter
    assert len(a) == 64  # sha-256 hex


def test_scenario_hash_changes_with_any_field() -> None:
    base = scenario_hash({"routine_id": "r", "scheme_id": "s"})
    assert scenario_hash({"routine_id": "r2", "scheme_id": "s"}) != base


def test_idempotency_key_folds_seed_and_engine_version() -> None:
    spec = {"routine_id": "r", "scheme_id": "s"}
    k = idempotency_key(spec, seed=7, engine_version="sim/0.4.0")
    assert k == idempotency_key(spec, seed=7, engine_version="sim/0.4.0")
    assert k != idempotency_key(spec, seed=8, engine_version="sim/0.4.0")
    assert k != idempotency_key(spec, seed=7, engine_version="sim/0.5.0")
    assert len(k) == 64


def test_nested_structures_are_canonicalized() -> None:
    a = scenario_hash({"runs": [{"x": 1, "y": 2}], "z": 3})
    b = scenario_hash({"z": 3, "runs": [{"y": 2, "x": 1}]})
    assert a == b

"""Postgres mart-loader tests - skipped unless a server is provided (ADR-007 d1).

Set ``RESTART_TEST_DATABASE_URL`` to a throwaway database to exercise them; CI
stays server-free. The contract under test is idempotency: loading the same
source twice leaves identical row counts (delete-by-source + insert).
"""

from __future__ import annotations

import os

import pytest

from restart_etl.marts.load_postgres import load_mart_postgres

pytestmark = pytest.mark.postgres

DSN = os.environ.get("RESTART_TEST_DATABASE_URL")
requires_pg = pytest.mark.skipif(not DSN, reason="no RESTART_TEST_DATABASE_URL")

_TABLE = "test_mart_load_postgres"
_ROWS = [
    {"source": "derived", "k": "a", "v": 1},
    {"source": "derived", "k": "b", "v": 2},
    {"source": "curated", "k": "c", "v": 3},
]


@requires_pg
def test_load_is_idempotent_per_source() -> None:
    assert DSN is not None
    psycopg = pytest.importorskip("psycopg")

    with psycopg.connect(DSN) as conn:
        conn.execute(f"DROP TABLE IF EXISTS {_TABLE}")
        conn.execute(f"CREATE TABLE {_TABLE} (source text, k text, v bigint)")
        conn.commit()

    derived = [r for r in _ROWS if r["source"] == "derived"]
    n1 = load_mart_postgres(DSN, _TABLE, derived, source="derived")
    n2 = load_mart_postgres(DSN, _TABLE, derived, source="derived")
    assert n1 == n2 == 2

    # Loading a different source must not disturb the first (DELETE WHERE source=X).
    load_mart_postgres(
        DSN, _TABLE, [r for r in _ROWS if r["source"] == "curated"], source="curated"
    )

    with psycopg.connect(DSN) as conn:
        total = conn.execute(f"SELECT count(*) FROM {_TABLE}").fetchone()
        conn.execute(f"DROP TABLE IF EXISTS {_TABLE}")
        conn.commit()
    assert total is not None and total[0] == 3

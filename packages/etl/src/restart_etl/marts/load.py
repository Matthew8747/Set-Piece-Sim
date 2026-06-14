"""Idempotent mart loader into a file-based DuckDB warehouse.

Marts are materialized as Parquet (the committed, license-audited products) and
also loaded into ``data/marts/restart.duckdb`` for SQL access. The load is
idempotent per design doc 04 §4 (``DELETE WHERE source=X`` + insert in a
transaction): re-running a single source's build never duplicates rows and never
disturbs other sources. A Postgres target is a drop-in here later (tech-debt
P4/6); the file-based engine keeps CI server-free.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

WAREHOUSE_FILE = "restart.duckdb"


def load_parquet_table(con: duckdb.DuckDBPyConnection, table: str, parquet: Path) -> int:
    """(Re)create ``table`` from a Parquet file; returns row count.

    Full-refresh semantics for whole-table marts. For multi-source marts use
    :func:`upsert_source` instead.
    """
    con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_parquet(?)", [str(parquet)])
    row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0]) if row else 0


def open_warehouse(marts_dir: Path) -> duckdb.DuckDBPyConnection:
    marts_dir.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(marts_dir / WAREHOUSE_FILE))

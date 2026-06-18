"""Idempotent Postgres mart loader — a drop-in beside the DuckDB loader (ADR-007 d1).

The default warehouse is file-based DuckDB (server-free CI). For a server
deployment the same committed mart Parquet is loaded into Postgres with the
design's idempotency contract (doc 04 §4): ``DELETE WHERE source = X`` then
insert, in a single transaction, so re-running one source never duplicates rows
and never disturbs another source.

``psycopg`` is an optional dependency (``restart-etl[postgres]``) imported lazily,
so the default install and CI stay server-free. Tests are skipped unless
``RESTART_TEST_DATABASE_URL`` is set.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pyarrow.parquet as pq

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pyarrow as pa

# The committed marts and the table each loads into (Parquet stem -> table name).
MART_TABLES: dict[str, str] = {
    "mart_players": "mart_players",
    "mart_player_attributes": "mart_player_attributes",
    "mart_setpiece_shots": "mart_setpiece_shots",
    "mart_defensive_schemes": "mart_defensive_schemes",
    "mart_calibration_targets": "mart_calibration_targets",
}


def _pg_type(arrow_type: pa.DataType) -> str:
    """Map an Arrow column type to a permissive Postgres column type."""
    import pyarrow as pa

    if pa.types.is_integer(arrow_type):
        return "BIGINT"
    if pa.types.is_floating(arrow_type):
        return "DOUBLE PRECISION"
    if pa.types.is_boolean(arrow_type):
        return "BOOLEAN"
    return "TEXT"


def _ensure_table(conn: Any, table: str, schema: pa.Schema) -> None:
    from psycopg import sql

    cols = [
        sql.SQL("{} {}").format(sql.Identifier(field.name), sql.SQL(_pg_type(field.type)))
        for field in schema
    ]
    conn.execute(
        sql.SQL("CREATE TABLE IF NOT EXISTS {tbl} ({cols})").format(
            tbl=sql.Identifier(table), cols=sql.SQL(", ").join(cols)
        )
    )


def load_mart_postgres(
    dsn: str,
    table: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    source: str,
    source_col: str = "source",
) -> int:
    """Idempotently load ``rows`` for one ``source`` into ``table``.

    Deletes the source's existing rows and inserts the new set in a transaction;
    returns the number of rows inserted. The table must already exist.
    """
    if not rows:
        return 0
    import psycopg
    from psycopg import sql

    cols = list(rows[0].keys())
    delete = sql.SQL("DELETE FROM {tbl} WHERE {col} = %s").format(
        tbl=sql.Identifier(table), col=sql.Identifier(source_col)
    )
    insert = sql.SQL("INSERT INTO {tbl} ({cols}) VALUES ({ph})").format(
        tbl=sql.Identifier(table),
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in cols),
        ph=sql.SQL(", ").join(sql.Placeholder() for _ in cols),
    )
    with psycopg.connect(dsn) as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute(delete, (source,))
        cur.executemany(insert, [[row[c] for c in cols] for row in rows])
    return len(rows)


def load_parquet_mart(dsn: str, table: str, parquet: Path, *, source_col: str = "source") -> int:
    """Load a mart Parquet into Postgres, idempotent per ``source`` value.

    Creates the table from the Parquet schema if absent, then re-loads each
    distinct ``source`` group. Marts without a ``source`` column are full-refreshed
    (delete-all + insert) inside a transaction.
    """
    arrow = pq.read_table(parquet)  # type: ignore[no-untyped-call]
    rows: list[dict[str, Any]] = arrow.to_pylist()

    import psycopg

    with psycopg.connect(dsn) as conn:
        _ensure_table(conn, table, arrow.schema)
        conn.commit()

    if source_col not in arrow.schema.names:
        return _full_refresh(dsn, table, rows)

    total = 0
    for source in sorted({str(r[source_col]) for r in rows}):
        group = [r for r in rows if str(r[source_col]) == source]
        total += load_mart_postgres(dsn, table, group, source=source, source_col=source_col)
    return total


def _full_refresh(dsn: str, table: str, rows: Sequence[Mapping[str, Any]]) -> int:
    if not rows:
        return 0
    import psycopg
    from psycopg import sql

    cols = list(rows[0].keys())
    insert = sql.SQL("INSERT INTO {tbl} ({cols}) VALUES ({ph})").format(
        tbl=sql.Identifier(table),
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in cols),
        ph=sql.SQL(", ").join(sql.Placeholder() for _ in cols),
    )
    with psycopg.connect(dsn) as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute(sql.SQL("DELETE FROM {tbl}").format(tbl=sql.Identifier(table)))
        cur.executemany(insert, [[row[c] for c in cols] for row in rows])
    return len(rows)


def load_all_marts_postgres(dsn: str, marts_dir: Path) -> dict[str, int]:
    """Load every committed mart Parquet into Postgres; returns table -> row count."""
    loaded: dict[str, int] = {}
    for stem, table in MART_TABLES.items():
        parquet = marts_dir / f"{stem}.parquet"
        if parquet.is_file():
            loaded[table] = load_parquet_mart(dsn, table, parquet)
    return loaded

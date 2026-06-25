"""Thin Parquet read/write helpers over pyarrow (row-dict <-> table).

Centralizes the pyarrow boundary so the rest of the package speaks plain Python
dicts. Nested/variable-length fields (e.g. a shot freeze frame) are carried as a
JSON string column - Parquet stays flat and the schema is trivially stable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


def write_rows(rows: list[dict[str, Any]], dest: Path) -> int:
    """Write a list of homogeneous row dicts to ``dest`` as Parquet. Returns rows."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows) if rows else pa.table({})
    pq.write_table(table, dest)  # type: ignore[no-untyped-call]
    return len(rows)


def read_rows(src: Path) -> list[dict[str, Any]]:
    """Read a Parquet file into a list of row dicts."""
    table = pq.read_table(src)  # type: ignore[no-untyped-call]
    result: list[dict[str, Any]] = table.to_pylist()
    return result


def to_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def from_json(text: str) -> Any:
    return json.loads(text)

"""Restart Lab ETL: StatsBomb Open Data -> raw -> staging -> marts.

Pure-data package (import name ``restart_etl``). It owns the data lake under
``data/`` and the ``restart-etl`` CLI. It does **not** import the simulation
core (``restart``) on the fetch/staging path: data ingestion and physics are
separate concerns. The xG training package (``restart_ml``) consumes the marts
this package produces.

Licensing (design doc 04 §2): StatsBomb Open Data is free for non-commercial
use *with attribution* and *prohibits raw redistribution* — which is why the
raw cache is git-ignored and only derived, source-tagged marts are committed.
Every mart row carries a ``source`` checked mechanically by the license gate.
"""

ETL_VERSION = "etl/0.1.0"

__all__ = ["ETL_VERSION"]

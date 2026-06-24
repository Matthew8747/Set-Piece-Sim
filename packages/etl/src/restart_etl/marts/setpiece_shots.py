"""``mart_setpiece_shots``: the real-data xG training table (design doc 04 §1).

One row per real corner/free-kick shot: geometry + freeze-frame traffic features
+ the binary goal label + grouping key (``match_id`` for leakage-safe CV). This
is System A's *only* training input - it never sees simulator output (doc 06 §1).
``statsbomb_xg`` is carried for sanity comparison but is neither a feature nor
the label.
"""

from __future__ import annotations

from typing import Any

from restart_etl.marts.features import compute_features
from restart_etl.pq import from_json

MART_FILE = "mart_setpiece_shots.parquet"

# Columns copied straight from staging (identity, grouping, categoricals).
_PASSTHROUGH = (
    "shot_id",
    "match_id",
    "competition",
    "team_id",
    "team",
    "player_id",
    "player",
    "set_piece_type",
    "set_piece_phase",
    "body_part_group",
    "shot_type",
    "technique",
    "under_pressure",
    "is_goal",
    "statsbomb_xg",
    "has_freeze_frame",
    "source",
)


def build_setpiece_shots(staging_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project staging shots into the feature-complete mart rows."""
    out: list[dict[str, Any]] = []
    for s in staging_rows:
        ff = from_json(s["freeze_frame"]) if s.get("freeze_frame") else []
        feats = compute_features(float(s["x_m"]), float(s["y_m"]), ff)
        row: dict[str, Any] = {k: s[k] for k in _PASSTHROUGH}
        row["x_m"] = float(s["x_m"])
        row["y_m"] = float(s["y_m"])
        row["is_header"] = 1 if s["body_part_group"] == "head" else 0
        row.update(feats.as_dict())
        out.append(row)
    return out

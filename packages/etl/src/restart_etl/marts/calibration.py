"""``mart_calibration_targets``: real-world base rates for engine calibration.

Per design doc 04 §1.2 these are the targets the simulator's ``[knob]`` params
are eventually fitted against (the owed week-5 calibration gate). Each row is a
(set_piece_type, phase) cell with its goal rate, header share, shot count and
sample size, so the calibration doc can pin "goal rate ~2-3% real" with evidence.
"""

from __future__ import annotations

from typing import Any

MART_FILE = "mart_calibration_targets.parquet"


def build_calibration_targets(shot_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate base rates per (set_piece_type, set_piece_phase) and overall."""
    cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for s in shot_rows:
        key = (s["set_piece_type"], s["set_piece_phase"])
        cells.setdefault(key, []).append(s)
        overall = (s["set_piece_type"], "all")
        cells.setdefault(overall, []).append(s)

    rows: list[dict[str, Any]] = []
    for (sp_type, phase), shots in sorted(cells.items()):
        n = len(shots)
        goals = sum(int(s["is_goal"]) for s in shots)
        headers = sum(1 for s in shots if s["body_part_group"] == "head")
        rows.append(
            {
                "set_piece_type": sp_type,
                "set_piece_phase": phase,
                "n_shots": n,
                "n_goals": goals,
                "goal_rate": (goals / n if n else 0.0),
                "header_share": (headers / n if n else 0.0),
                "source": "statsbomb_open_data",
            }
        )
    return rows

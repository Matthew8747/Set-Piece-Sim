"""``mart_defensive_schemes``: how teams defend corners (design doc 04 §1.4).

A small curated library of canonical schemes (zonal / man / hybrid) with their
marker counts, informed by an empirical summary of real corner freeze frames
(average opponents in the box at the shot). Curated rows are tagged ``curated``;
the empirical reference row is tagged ``statsbomb_open_data``.
"""

from __future__ import annotations

from typing import Any

MART_FILE = "mart_defensive_schemes.parquet"

# Canonical schemes. n_zonal/n_man/n_edge are typical marker allocations for a
# defending side at a corner (10 outfielders + GK); descriptions are analyst
# curation, not measurements.
_CURATED: list[dict[str, Any]] = [
    {
        "scheme": "zonal",
        "scheme_type": "zonal",
        "n_zonal": 8,
        "n_man": 0,
        "n_edge": 2,
        "description": "Pure zonal: defenders occupy key zones, attack the ball not a man.",
    },
    {
        "scheme": "man",
        "scheme_type": "man",
        "n_zonal": 1,
        "n_man": 7,
        "n_edge": 2,
        "description": "Man-marking: each threat tracked individually, one post zonal anchor.",
    },
    {
        "scheme": "hybrid",
        "scheme_type": "hybrid",
        "n_zonal": 4,
        "n_man": 4,
        "n_edge": 2,
        "description": "Hybrid: zonal core in the six-yard box plus man-marking on aerial threats.",
    },
]


def build_defensive_schemes(setpiece_shot_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for s in _CURATED:
        rows.append({**s, "n_shots": 0, "source": "curated"})

    corners = [
        r
        for r in setpiece_shot_rows
        if r["set_piece_type"] == "corner" and bool(r.get("has_freeze_frame"))
    ]
    if corners:
        avg_box = sum(int(r["n_def_in_box"]) for r in corners) / len(corners)
        avg_cone = sum(int(r["defenders_in_cone"]) for r in corners) / len(corners)
        rows.append(
            {
                "scheme": "empirical_corner_reference",
                "scheme_type": "empirical",
                "n_zonal": round(avg_box),
                "n_man": 0,
                "n_edge": 0,
                "description": (
                    f"Observed corner shots: avg {avg_box:.1f} defenders in box, "
                    f"{avg_cone:.1f} in the shooting cone (freeze-frame derived)."
                ),
                "n_shots": len(corners),
                "source": "statsbomb_open_data",
            }
        )
    return rows

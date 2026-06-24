"""CI check: every mart column is documented in docs/data-dictionary.md.

Mechanical enforcement of design doc 04 §6 - no field reachable as a mart product
may be absent from the dictionary. The check builds each mart from a minimal
synthetic input and asserts every emitted column name appears in the doc.
"""

from __future__ import annotations

from typing import Any

from restart_etl.config import repo_root
from restart_etl.marts import calibration, schemes, setpiece_shots
from restart_etl.marts.players import PlayerAccumulator
from restart_etl.pq import to_json


def _staging_row() -> dict[str, Any]:
    ff = [
        {"x_m": 50.0, "y_m": 0.5, "teammate": False, "is_gk": True},
        {"x_m": 48.0, "y_m": 1.0, "teammate": False, "is_gk": False},
        {"x_m": 47.0, "y_m": -1.0, "teammate": True, "is_gk": False},
    ]
    return {
        "shot_id": "a",
        "match_id": 1,
        "competition": "wc2022",
        "team_id": 1,
        "team": "A",
        "player_id": 9,
        "player": "P",
        "set_piece_type": "corner",
        "set_piece_phase": "first_contact",
        "body_part_group": "head",
        "shot_type": "Open Play",
        "technique": "Normal",
        "under_pressure": True,
        "is_goal": 1,
        "statsbomb_xg": 0.2,
        "has_freeze_frame": True,
        "source": "statsbomb_open_data",
        "x_m": 47.0,
        "y_m": 0.0,
        "freeze_frame": to_json(ff),
    }


def _all_mart_columns() -> set[str]:
    staging = [_staging_row()]
    cols: set[str] = set()
    cols |= set(setpiece_shots.build_setpiece_shots(staging)[0])
    cols |= set(calibration.build_calibration_targets(staging)[0])
    shots = setpiece_shots.build_setpiece_shots(staging)
    cols |= set(schemes.build_defensive_schemes(shots)[0])

    acc = PlayerAccumulator()
    acc.observe_lineup(
        [
            {
                "team_name": "A",
                "team_id": 1,
                "lineup": [
                    {
                        "player_id": 9,
                        "player_name": "P",
                        "country": {"name": "X"},
                        "positions": [{"position": "Center Forward"}],
                    }
                ],
            }
        ]
    )
    players, attributes = acc.finalize()
    cols |= set(players[0])
    cols |= set(attributes[0])
    return cols


def test_every_mart_column_is_documented() -> None:
    doc = (repo_root() / "docs" / "data-dictionary.md").read_text(encoding="utf-8")
    missing = sorted(col for col in _all_mart_columns() if f"`{col}`" not in doc)
    assert not missing, f"undocumented mart columns: {missing}"

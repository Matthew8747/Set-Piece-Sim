"""License + distribution gate behavior on synthetic mart rows."""

from __future__ import annotations

from typing import Any

from restart_etl.config import DataPaths
from restart_etl.marts import calibration, players, schemes, setpiece_shots
from restart_etl.pq import write_rows
from restart_etl.quality.gates import Severity, _license_audit, run_gates


def test_license_audit_flags_forbidden_source() -> None:
    findings: list[Any] = []
    _license_audit([{"source": "sofifa"}], "mart_x", findings)
    assert any(f.severity is Severity.FAIL for f in findings)


def test_license_audit_passes_approved() -> None:
    findings: list[Any] = []
    _license_audit([{"source": "statsbomb_open_data"}], "mart_x", findings)
    assert all(f.severity is not Severity.FAIL for f in findings)


def _shot(
    is_goal: int, x: float = 45.0, y: float = 0.0, source: str = "statsbomb_open_data"
) -> dict[str, Any]:
    return {
        "x_m": x,
        "y_m": y,
        "is_goal": is_goal,
        "n_defenders": 4,
        "n_teammates": 5,
        "defenders_in_cone": 1,
        "n_def_in_box": 3,
        "has_freeze_frame": True,
        "set_piece_type": "corner",
        "source": source,
    }


def test_run_gates_pass_and_fail(tmp_path: Any) -> None:
    paths = DataPaths(root=tmp_path)
    paths.ensure()
    # ~6% goal rate, in band, on-pitch.
    shots = [_shot(1)] * 30 + [_shot(0)] * 470
    write_rows(shots, paths.marts / setpiece_shots.MART_FILE)
    write_rows(
        [
            {
                "set_piece_type": "corner",
                "set_piece_phase": "all",
                "n_shots": 500,
                "n_goals": 30,
                "goal_rate": 0.06,
                "header_share": 0.5,
                "source": "statsbomb_open_data",
            }
        ],
        paths.marts / calibration.MART_FILE,
    )
    write_rows(
        [
            {
                "player_id": 1,
                "player": "X",
                "team": "A",
                "attribute": "heading",
                "value": 0.5,
                "unit": "0-1",
                "source": "derived",
                "method": "m",
                "license": "l",
            }
        ],
        paths.marts / players.ATTRIBUTES_FILE,
    )
    write_rows(
        [
            {
                "scheme": "zonal",
                "scheme_type": "zonal",
                "n_zonal": 8,
                "n_man": 0,
                "n_edge": 2,
                "description": "",
                "n_shots": 0,
                "source": "curated",
            }
        ],
        paths.marts / schemes.MART_FILE,
    )
    report = run_gates(paths)
    assert report.passed

    # Inject an off-pitch shot -> coords FAIL.
    bad = [*shots, _shot(0, x=200.0)]
    write_rows(bad, paths.marts / setpiece_shots.MART_FILE)
    report2 = run_gates(paths)
    assert not report2.passed

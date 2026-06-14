"""Build all marts from staging + the raw cache, then load DuckDB.

Order: setpiece_shots and calibration come from the staging shot table; players
and attributes need a second pass over raw events (aerial duels, deliveries);
defensive_schemes summarizes the shot mart. Everything is materialized to
Parquet (the committed products) and loaded into the file-based warehouse.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from restart_etl.config import DataPaths
from restart_etl.marts import calibration, players, schemes, setpiece_shots
from restart_etl.marts.load import load_parquet_table, open_warehouse
from restart_etl.pq import read_rows, write_rows
from restart_etl.staging.build import STAGING_SHOTS_FILE

ProgressFn = Callable[[str], None]


def _noop(_: str) -> None:  # pragma: no cover
    pass


@dataclass(frozen=True, slots=True)
class MartResult:
    setpiece_shots: int
    calibration_cells: int
    players: int
    player_attributes: int
    defensive_schemes: int


def _iter_match_events(paths: DataPaths) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
    """Return (all_events_with_match_id, per_match_lineups) from the raw cache."""
    matches_dir = paths.statsbomb_raw / "matches"
    events_dir = paths.statsbomb_raw / "events"
    lineups_dir = paths.statsbomb_raw / "lineups"
    events: list[dict[str, Any]] = []
    lineups: list[list[dict[str, Any]]] = []
    for mf in sorted(matches_dir.glob("*.json")):
        matches = json.loads(mf.read_text(encoding="utf-8"))
        for m in matches:
            mid = int(m["match_id"])
            ev_file = events_dir / f"{mid}.json"
            lu_file = lineups_dir / f"{mid}.json"
            if ev_file.is_file():
                events.extend(json.loads(ev_file.read_text(encoding="utf-8")))
            if lu_file.is_file():
                lineups.append(json.loads(lu_file.read_text(encoding="utf-8")))
    return events, lineups


def run_marts(paths: DataPaths, *, progress: ProgressFn | None = None) -> MartResult:
    echo = progress if progress is not None else _noop
    paths.ensure()
    staging_file = paths.staging / STAGING_SHOTS_FILE
    if not staging_file.is_file():
        raise FileNotFoundError(
            f"no staging shots at {staging_file}; run `restart-etl stage` first"
        )

    staging_rows = read_rows(staging_file)
    shot_rows = setpiece_shots.build_setpiece_shots(staging_rows)
    write_rows(shot_rows, paths.marts / setpiece_shots.MART_FILE)
    echo(f"mart_setpiece_shots: {len(shot_rows)} rows")

    calib_rows = calibration.build_calibration_targets(staging_rows)
    write_rows(calib_rows, paths.marts / calibration.MART_FILE)
    echo(f"mart_calibration_targets: {len(calib_rows)} cells")

    scheme_rows = schemes.build_defensive_schemes(shot_rows)
    write_rows(scheme_rows, paths.marts / schemes.MART_FILE)
    echo(f"mart_defensive_schemes: {len(scheme_rows)} rows")

    echo("scanning raw events for player aggregates...")
    all_events, all_lineups = _iter_match_events(paths)
    acc = players.PlayerAccumulator()
    for lu in all_lineups:
        acc.observe_lineup(lu)
    for ev in all_events:
        acc.observe_event(ev)
    player_rows, attr_rows = acc.finalize()
    write_rows(player_rows, paths.marts / players.PLAYERS_FILE)
    write_rows(attr_rows, paths.marts / players.ATTRIBUTES_FILE)
    echo(f"mart_players: {len(player_rows)} players, {len(attr_rows)} attribute rows")

    # Load the file-based warehouse (full-refresh of each whole-table mart).
    con = open_warehouse(paths.marts)
    try:
        for table, mart_file in (
            ("mart_setpiece_shots", setpiece_shots.MART_FILE),
            ("mart_calibration_targets", calibration.MART_FILE),
            ("mart_defensive_schemes", schemes.MART_FILE),
            ("mart_players", players.PLAYERS_FILE),
            ("mart_player_attributes", players.ATTRIBUTES_FILE),
        ):
            load_parquet_table(con, table, paths.marts / mart_file)
    finally:
        con.close()

    return MartResult(
        setpiece_shots=len(shot_rows),
        calibration_cells=len(calib_rows),
        players=len(player_rows),
        player_attributes=len(attr_rows),
        defensive_schemes=len(scheme_rows),
    )

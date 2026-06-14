"""Build the staging layer from the raw StatsBomb cache.

Walks the cached match files, extracts corner and free-kick **shots**, applies
the one coordinate transform, classifies set-piece type/phase/body-part, and
writes typed Parquet. Runs offline against the raw cache (no network), so CI can
exercise it on a frozen fixture snapshot.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from restart_etl.config import COMPETITIONS, DataPaths
from restart_etl.pq import to_json, write_rows
from restart_etl.staging.models import FreezeFramePlayer, StagingShot
from restart_etl.transforms.coords import to_pitch_xy

ProgressFn = Callable[[str], None]


def _noop(_: str) -> None:  # pragma: no cover
    pass


# StatsBomb body part -> grouped category (drives the header/foot model split).
_BODY_GROUP = {
    "Right Foot": "foot",
    "Left Foot": "foot",
    "Head": "head",
    "Other": "other",
}
_FIRST_CONTACT_TECHNIQUES = {"Volley", "Half Volley", "Overhead Kick", "Diving Header"}

STAGING_SHOTS_FILE = "setpiece_shots.parquet"


@dataclass(frozen=True, slots=True)
class StagingResult:
    event_rows: int
    shot_rows: int


def _competition_alias(competition_id: int, season_id: int) -> str:
    for alias, comp in COMPETITIONS.items():
        if comp.competition_id == competition_id and comp.season_id == season_id:
            return alias
    return f"{competition_id}_{season_id}"


def _set_piece_type(play_pattern: str, shot_type: str) -> str | None:
    if shot_type == "Corner":
        return "corner"
    if shot_type == "Free Kick":
        return "free_kick"
    if play_pattern == "From Corner":
        return "corner"
    if play_pattern == "From Free Kick":
        return "free_kick"
    return None


def _phase(shot_type: str, body_group: str, technique: str) -> str:
    if shot_type in ("Free Kick", "Corner"):
        return "direct"
    if body_group == "head" or technique in _FIRST_CONTACT_TECHNIQUES:
        return "first_contact"
    return "second_ball"


def _freeze_frame(raw_ff: list[dict[str, Any]]) -> list[FreezeFramePlayer]:
    players: list[FreezeFramePlayer] = []
    for p in raw_ff:
        loc = p.get("location")
        if not loc or len(loc) < 2:
            continue
        x_m, y_m = to_pitch_xy(float(loc[0]), float(loc[1]))
        pos = p.get("position", {}).get("name", "")
        players.append(
            FreezeFramePlayer(
                x_m=x_m,
                y_m=y_m,
                teammate=bool(p.get("teammate", False)),
                is_gk=(pos == "Goalkeeper"),
            )
        )
    return players


def _shot_to_staging(event: dict[str, Any], competition: str) -> StagingShot | None:
    if event.get("type", {}).get("name") != "Shot":
        return None
    shot = event.get("shot", {})
    shot_type = shot.get("type", {}).get("name", "")
    if shot_type == "Penalty":
        return None
    play_pattern = event.get("play_pattern", {}).get("name", "")
    sp_type = _set_piece_type(play_pattern, shot_type)
    if sp_type is None:
        return None

    loc = event.get("location")
    if not loc or len(loc) < 2:
        return None
    x_m, y_m = to_pitch_xy(float(loc[0]), float(loc[1]))

    end = shot.get("end_location")
    end_x_m: float | None = None
    end_y_m: float | None = None
    if end and len(end) >= 2:
        end_x_m, end_y_m = to_pitch_xy(float(end[0]), float(end[1]))

    body_part = shot.get("body_part", {}).get("name", "Other")
    body_group = _BODY_GROUP.get(body_part, "other")
    technique = shot.get("technique", {}).get("name", "Normal")
    phase = _phase(shot_type, body_group, technique)
    outcome = shot.get("outcome", {}).get("name", "")
    raw_ff = shot.get("freeze_frame", []) or []
    ff = _freeze_frame(raw_ff)

    return StagingShot(
        shot_id=str(event["id"]),
        match_id=int(event["__match_id"]),
        competition=competition,
        period=int(event.get("period", 0)),
        minute=int(event.get("minute", 0)),
        second=int(event.get("second", 0)),
        team_id=int(event.get("team", {}).get("id", 0)),
        team=str(event.get("team", {}).get("name", "")),
        player_id=int(event.get("player", {}).get("id", 0)),
        player=str(event.get("player", {}).get("name", "")),
        position=str(event.get("position", {}).get("name", "")),
        play_pattern=play_pattern,
        set_piece_type=sp_type,
        set_piece_phase=phase,
        shot_type=shot_type,
        body_part=body_part,
        body_part_group=body_group,
        technique=technique,
        outcome=outcome,
        is_goal=1 if outcome == "Goal" else 0,
        x_m=x_m,
        y_m=y_m,
        end_x_m=end_x_m,
        end_y_m=end_y_m,
        statsbomb_xg=(float(shot["statsbomb_xg"]) if "statsbomb_xg" in shot else None),
        under_pressure=bool(event.get("under_pressure", False)),
        freeze_frame=ff,
        has_freeze_frame=len(ff) > 0,
    )


def _staging_row(shot: StagingShot) -> dict[str, Any]:
    row = shot.model_dump()
    # Carry the freeze frame as a compact JSON column (keeps Parquet flat).
    row["freeze_frame"] = to_json([p.model_dump() for p in shot.freeze_frame])
    return row


def run_staging(paths: DataPaths, *, progress: ProgressFn | None = None) -> StagingResult:
    echo = progress if progress is not None else _noop
    paths.ensure()
    matches_dir = paths.statsbomb_raw / "matches"
    events_dir = paths.statsbomb_raw / "events"
    if not matches_dir.is_dir():
        raise FileNotFoundError(f"no raw matches at {matches_dir}; run `restart-etl fetch` first")

    rows: list[dict[str, Any]] = []
    event_count = 0
    match_files = sorted(matches_dir.glob("*.json"))
    for mf in match_files:
        comp_id, season_id = (int(x) for x in mf.stem.split("_"))
        competition = _competition_alias(comp_id, season_id)
        matches = json.loads(mf.read_text(encoding="utf-8"))
        match_ids = [int(m["match_id"]) for m in matches]
        echo(f"staging {competition}: {len(match_ids)} matches")
        for mid in match_ids:
            ev_file = events_dir / f"{mid}.json"
            if not ev_file.is_file():
                continue
            events = json.loads(ev_file.read_text(encoding="utf-8"))
            event_count += len(events)
            for ev in events:
                ev["__match_id"] = mid
                staged = _shot_to_staging(ev, competition)
                if staged is not None:
                    rows.append(_staging_row(staged))

    dest = paths.staging / STAGING_SHOTS_FILE
    write_rows(rows, dest)
    echo(f"wrote {len(rows)} set-piece shots -> {dest}")
    return StagingResult(event_rows=event_count, shot_rows=len(rows))

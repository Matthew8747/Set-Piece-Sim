"""Set-piece classification at the staging boundary."""

from __future__ import annotations

from typing import Any

from restart_etl.staging.build import _phase, _set_piece_type, _shot_to_staging


def test_set_piece_type_resolution() -> None:
    assert _set_piece_type("From Corner", "Open Play") == "corner"
    assert _set_piece_type("From Free Kick", "Open Play") == "free_kick"
    assert _set_piece_type("Regular Play", "Corner") == "corner"
    assert _set_piece_type("Regular Play", "Free Kick") == "free_kick"
    assert _set_piece_type("From Throw In", "Open Play") is None
    assert _set_piece_type("Regular Play", "Open Play") is None


def test_phase_classification() -> None:
    assert _phase("Free Kick", "foot", "Normal") == "direct"
    assert _phase("Open Play", "head", "Normal") == "first_contact"
    assert _phase("Open Play", "foot", "Volley") == "first_contact"
    assert _phase("Open Play", "foot", "Normal") == "second_ball"


def _shot_event(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "abc",
        "__match_id": 1,
        "type": {"name": "Shot"},
        "play_pattern": {"name": "From Corner"},
        "location": [110.0, 40.0],
        "team": {"id": 1, "name": "A"},
        "player": {"id": 9, "name": "Striker"},
        "position": {"name": "Center Forward"},
        "period": 1,
        "minute": 10,
        "second": 5,
        "shot": {
            "type": {"name": "Open Play"},
            "body_part": {"name": "Head"},
            "technique": {"name": "Normal"},
            "outcome": {"name": "Goal"},
            "statsbomb_xg": 0.2,
            "freeze_frame": [
                {"location": [118.0, 40.0], "teammate": False, "position": {"name": "Goalkeeper"}},
                {"location": [112.0, 41.0], "teammate": False, "position": {"name": "Center Back"}},
            ],
        },
    }
    base.update(over)
    return base


def test_corner_header_goal_staged() -> None:
    staged = _shot_to_staging(_shot_event(), "wc2022")
    assert staged is not None
    assert staged.set_piece_type == "corner"
    assert staged.set_piece_phase == "first_contact"
    assert staged.body_part_group == "head"
    assert staged.is_goal == 1
    assert staged.has_freeze_frame
    assert len(staged.freeze_frame) == 2
    assert any(p.is_gk for p in staged.freeze_frame)


def test_open_play_shot_rejected() -> None:
    ev = _shot_event(play_pattern={"name": "Regular Play"})
    ev["shot"]["type"] = {"name": "Open Play"}
    assert _shot_to_staging(ev, "wc2022") is None


def test_penalty_rejected() -> None:
    ev = _shot_event()
    ev["shot"]["type"] = {"name": "Penalty"}
    assert _shot_to_staging(ev, "wc2022") is None

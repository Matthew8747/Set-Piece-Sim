# Data Dictionary v1 - Restart Lab marts

Every column reachable as a mart product is documented here. The mechanical check
`packages/etl/tests/test_etl_data_dictionary.py` walks the mart builders' output
columns and fails CI if any is undocumented (design doc 04 §6 acceptance).

Coordinate frame everywhere: **105×68 m, origin at pitch centre, attack left→right**
(attacking goal at x = +52.5; `restart_etl.transforms.coords`). All set-piece data
derives from **StatsBomb Open Data** (non-commercial, attribution required); the raw
cache is git-ignored (no raw redistribution) and rebuildable via `restart-etl`.

## `mart_setpiece_shots` - xG training table

One row per real corner/free-kick shot. License: StatsBomb Open Data (`source`).

| Column | Type | Units | Meaning |
|---|---|---|---|
| `shot_id` | str | - | StatsBomb event id |
| `match_id` | int | - | StatsBomb match id; the **CV grouping key** (leakage guard) |
| `competition` | str | - | competition alias (e.g. `wc2022`, `euro2024`) |
| `team_id`, `team` | int, str | - | shooting team |
| `player_id`, `player` | int, str | - | shooter |
| `set_piece_type` | str | - | `corner` \| `free_kick` |
| `set_piece_phase` | str | - | `direct` \| `first_contact` \| `second_ball` |
| `body_part_group` | str | - | `foot` \| `head` \| `other` (drives the header/foot model split) |
| `shot_type` | str | - | raw StatsBomb shot type (Open Play / Free Kick / Corner) |
| `technique` | str | - | raw StatsBomb technique (Volley, Half Volley, …) |
| `under_pressure` | bool | - | defender pressure flag at the shot |
| `is_goal` | int | 0/1 | **label**: 1 iff outcome = Goal |
| `is_header` | int | 0/1 | header convenience flag (= body_part_group head) |
| `statsbomb_xg` | float? | prob | StatsBomb's own xG - **reference only**, never a feature or label |
| `has_freeze_frame` | bool | - | a freeze frame was present (else traffic features are 0) |
| `x_m`, `y_m` | float | m | shot location, canonical frame |
| `distance_m` | float | m | distance to goal centre |
| `angle_rad` | float | rad | goal-mouth opening angle from the shot |
| `defenders_in_cone` | int | - | opponents (excl. GK) inside the shot→posts triangle |
| `nearest_def_dist_m` | float | m | distance to nearest outfield opponent |
| `defenders_within_3m` | int | - | outfield opponents within 3 m |
| `n_defenders`, `n_teammates` | int | - | freeze-frame opponent / teammate counts |
| `n_def_in_box` | int | - | opponents inside the penalty area |
| `gk_dist_to_goal_m` | float | m | keeper distance to goal centre (depth proxy) |
| `gk_dist_to_shot_m` | float | m | keeper distance to the shot location |
| `gk_lateral_m` | float | m | keeper lateral offset from goal centre |
| `has_gk` | bool | - | a goalkeeper was present in the freeze frame |
| `source` | str | - | `statsbomb_open_data` |

## `mart_calibration_targets` - real base rates

| Column | Type | Meaning |
|---|---|---|
| `set_piece_type` | str | `corner` \| `free_kick` |
| `set_piece_phase` | str | phase, plus an `all` rollup per type |
| `n_shots`, `n_goals` | int | sample sizes |
| `goal_rate` | float | goals / shots (the calibration target) |
| `header_share` | float | header fraction of shots |
| `source` | str | `statsbomb_open_data` |

## `mart_players` - squad identities

| Column | Type | Meaning |
|---|---|---|
| `player_id`, `player` | int, str | StatsBomb identity (nickname preferred) |
| `team`, `team_id`, `country` | str, int, str | affiliation |
| `primary_position` | str | modal lineup position |
| `position_group` | str | GK/DEF/DM/MID/ATT/WING/FWD |
| `aerial_won`, `aerial_lost` | int | head-contact / aerial-lost-duel counts (heading inputs) |
| `delivery_attempts` | int | corner/FK/cross passes attempted |
| `source` | str | `statsbomb_open_data` |

## `mart_player_attributes` - derived, provenance-tagged (long format)

One row per (player, attribute). Attribute names + units mirror
`restart.players.attributes` and are clamped to its bounds.

| Column | Type | Meaning |
|---|---|---|
| `player_id`, `player`, `team` | int, str, str | identity |
| `attribute` | str | engine attribute name (`heading`, `delivery`, `top_speed_ms`, `jump_reach_m`, `height_m`, …) |
| `value` | float | derived value (bounds-clamped) |
| `unit` | str | `m/s`, `m/s^2`, `s`, `m`, or `0-1` |
| `source` | str | `derived` \| `literature_prior` \| `curated` |
| `method` | str | the documented derivation (e.g. "aerial win rate …, EB-shrunk to DEF prior") |
| `license` | str | provenance license string (the UI badge text) |

## `mart_defensive_schemes` - corner defence library

| Column | Type | Meaning |
|---|---|---|
| `scheme` | str | scheme id |
| `scheme_type` | str | `zonal` \| `man` \| `hybrid` \| `empirical` |
| `n_zonal`, `n_man`, `n_edge` | int | typical marker allocation |
| `description` | str | analyst description / empirical summary |
| `n_shots` | int | observed corner shots backing an empirical row (0 for curated) |
| `source` | str | `curated` \| `statsbomb_open_data` |

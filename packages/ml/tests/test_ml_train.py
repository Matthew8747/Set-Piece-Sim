"""xG training pipeline on a synthetic mart (independent of the raw data cache)."""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any

from restart.engine.xg import LogisticXGScorer, ShotContext, XGModelBundle
from restart_etl.marts import setpiece_shots
from restart_etl.pq import write_rows
from restart_ml.artifacts import load_active_bundle
from restart_ml.data import build_dataset
from restart_ml.fit import fit_logistic_scorer
from restart_ml.train import train_xg


def _synthetic_mart(path: Path, n_matches: int = 16, per_match: int = 14) -> None:
    rng = random.Random(7)
    rows: list[dict[str, Any]] = []
    for match in range(n_matches):
        for _ in range(per_match):
            dist = rng.uniform(3.0, 22.0)
            is_header = rng.random() < 0.4
            # Closer shots score more often; headers a touch less.
            p = 1.0 / (1.0 + math.exp(0.35 * (dist - 8.0) + (0.4 if is_header else 0.0)))
            goal = 1 if rng.random() < p else 0
            rows.append(
                {
                    "shot_id": f"{match}-{_}",
                    "match_id": match,
                    "competition": "synthetic",
                    "team_id": 1,
                    "team": "T",
                    "player_id": 1,
                    "player": "P",
                    "set_piece_type": "corner",
                    "set_piece_phase": "first_contact" if is_header else "second_ball",
                    "body_part_group": "head" if is_header else "foot",
                    "shot_type": "Open Play",
                    "technique": "Normal",
                    "under_pressure": rng.random() < 0.5,
                    "is_goal": goal,
                    "statsbomb_xg": p,
                    "has_freeze_frame": True,
                    "source": "statsbomb_open_data",
                    "x_m": 52.5 - dist,
                    "y_m": rng.uniform(-6, 6),
                    "is_header": 1 if is_header else 0,
                    "distance_m": dist,
                    "angle_rad": rng.uniform(0.1, 1.2),
                    "defenders_in_cone": rng.randint(0, 3),
                    "nearest_def_dist_m": rng.uniform(0.5, 6.0),
                    "defenders_within_3m": rng.randint(0, 2),
                    "n_defenders": rng.randint(3, 9),
                    "n_teammates": rng.randint(3, 8),
                    "n_def_in_box": rng.randint(2, 8),
                    "gk_dist_to_goal_m": rng.uniform(0.3, 2.5),
                    "gk_dist_to_shot_m": dist,
                    "gk_lateral_m": rng.uniform(0.0, 1.5),
                    "has_gk": True,
                }
            )
    write_rows(rows, path)


def test_build_dataset_splits_by_body_part(tmp_path: Path) -> None:
    mart = tmp_path / setpiece_shots.MART_FILE
    _synthetic_mart(mart)
    from restart_etl.pq import read_rows

    rows = read_rows(mart)
    head = build_dataset(rows, headers=True)
    foot = build_dataset(rows, headers=False)
    assert head.n > 0 and foot.n > 0
    assert head.n + foot.n == len(rows)
    assert head.model_id == "xg-header"


def test_fit_scorer_recovers_distance_signal(tmp_path: Path) -> None:
    mart = tmp_path / setpiece_shots.MART_FILE
    _synthetic_mart(mart)
    from restart_etl.pq import read_rows

    foot = build_dataset(read_rows(mart), headers=False)
    fitted = fit_logistic_scorer(foot, n_splits=3)
    near = _ctx(distance=5.0)
    far = _ctx(distance=20.0)
    assert fitted.scorer.score(near) > fitted.scorer.score(far)
    for ctx in (near, far):
        assert 0.0 <= fitted.scorer.score(ctx) <= 1.0


def test_train_writes_loadable_bundle(tmp_path: Path) -> None:
    mart = tmp_path / setpiece_shots.MART_FILE
    _synthetic_mart(mart)
    out = tmp_path / "models"
    result = train_xg(mart_path=mart, out_dir=out, n_splits=3, use_mlflow=False)
    assert result.bundle_path.is_file()
    bundle = load_active_bundle(out)
    assert isinstance(bundle, XGModelBundle)
    assert isinstance(bundle.header, LogisticXGScorer)
    assert 0.0 <= bundle.score(_ctx(distance=6.0, header=True)) <= 1.0
    # Comparison swept multiple candidates including the logistic baseline.
    assert "logreg" in result.foot.comparison


def _ctx(distance: float = 8.0, header: bool = False) -> ShotContext:
    return ShotContext(
        distance_m=distance,
        angle_rad=0.6,
        is_header=header,
        set_piece_phase="first_contact",
        defenders_in_cone=1,
        nearest_def_dist_m=2.0,
        defenders_within_3m=1,
        gk_dist_to_goal_m=1.0,
        gk_lateral_m=0.3,
        under_pressure=True,
    )

"""Load the real-data mart and build leakage-safe design matrices.

The feature surface is imported from the simulation core
(``restart.engine.xg.shot_feature_vector``) so training features are *identical*
to what the engine computes at score time - the train/serve contract is one
function, not two parallel implementations (design doc 06 §2.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from restart.engine.xg import ShotContext, shot_feature_vector
from restart_etl.config import default_paths
from restart_etl.marts import setpiece_shots
from restart_etl.pq import read_rows

FloatArr = npt.NDArray[np.float64]
IntArr = npt.NDArray[np.int64]

# Feature subsets per model (each is a body-part split, so is_header /
# header_x_distance are constant and dropped). Names index shot_feature_vector.
FEATURES_FOOT: tuple[str, ...] = (
    "distance",
    "inv_distance",
    "angle",
    "angle_sq",
    "defenders_in_cone",
    "nearest_def_dist",
    "defenders_within_3m",
    "gk_dist_to_goal",
    "gk_lateral",
    "under_pressure",
    "phase_first_contact",
    "phase_second_ball",
    "cone_x_inv_distance",
)
FEATURES_HEADER: tuple[str, ...] = (
    "distance",
    "inv_distance",
    "angle",
    "angle_sq",
    "defenders_in_cone",
    "nearest_def_dist",
    "defenders_within_3m",
    "gk_dist_to_goal",
    "gk_lateral",
    "under_pressure",
    "cone_x_inv_distance",
)


def default_mart_path() -> Path:
    return default_paths().marts / setpiece_shots.MART_FILE


def row_to_context(row: dict[str, Any]) -> ShotContext:
    """Reconstruct the engine's ShotContext from a mart row (same quantities)."""
    return ShotContext(
        distance_m=float(row["distance_m"]),
        angle_rad=float(row["angle_rad"]),
        is_header=bool(int(row["is_header"])),
        set_piece_phase=str(row["set_piece_phase"]),
        defenders_in_cone=int(row["defenders_in_cone"]),
        nearest_def_dist_m=float(row["nearest_def_dist_m"]),
        defenders_within_3m=int(row["defenders_within_3m"]),
        gk_dist_to_goal_m=float(row["gk_dist_to_goal_m"]),
        gk_lateral_m=float(row["gk_lateral_m"]),
        under_pressure=bool(row["under_pressure"]),
    )


@dataclass(frozen=True, slots=True)
class Dataset:
    x: FloatArr  # (n, k)
    y: IntArr  # (n,) goal label
    groups: IntArr  # (n,) match_id for GroupKFold
    feature_names: tuple[str, ...]
    model_id: str  # 'xg-header' | 'xg-foot'

    @property
    def n(self) -> int:
        return int(self.x.shape[0])

    @property
    def base_rate(self) -> float:
        return float(self.y.mean()) if self.n else 0.0


def build_dataset(rows: list[dict[str, Any]], *, headers: bool) -> Dataset:
    """Build a header or foot dataset (only rows with a freeze frame, so traffic
    features are real rather than imputed)."""
    feature_names = FEATURES_HEADER if headers else FEATURES_FOOT
    model_id = "xg-header" if headers else "xg-foot"
    xs: list[list[float]] = []
    ys: list[int] = []
    gs: list[int] = []
    for row in rows:
        is_head = bool(int(row["is_header"]))
        if is_head != headers:
            continue
        if not bool(row.get("has_freeze_frame")):
            continue
        feats = shot_feature_vector(row_to_context(row))
        xs.append([feats[name] for name in feature_names])
        ys.append(int(row["is_goal"]))
        gs.append(int(row["match_id"]))
    return Dataset(
        x=np.asarray(xs, dtype=np.float64).reshape(-1, len(feature_names)),
        y=np.asarray(ys, dtype=np.int64),
        groups=np.asarray(gs, dtype=np.int64),
        feature_names=feature_names,
        model_id=model_id,
    )


def load_datasets(mart_path: Path | None = None) -> tuple[Dataset, Dataset]:
    """Return (header_dataset, foot_dataset) from the mart."""
    path = mart_path if mart_path is not None else default_mart_path()
    rows = read_rows(path)
    return build_dataset(rows, headers=True), build_dataset(rows, headers=False)

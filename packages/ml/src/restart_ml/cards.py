"""Model-card generation (Google model-card schema; design doc 06 §2.4).

Renders a markdown card capturing data + license, the method comparison, the
shipped model's calibration evidence, intended use, and limitations — the
governance artifact the UI later renders and the interview talking-point.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from restart import ENGINE_VERSION
from restart_ml import ML_VERSION
from restart_ml.train import SplitResult, TrainResult

_COMPARISON_COLS = ("log_loss", "brier", "auc", "cal_slope", "cal_intercept", "n")


def _comparison_table(split: SplitResult) -> str:
    header = "| candidate | " + " | ".join(_COMPARISON_COLS) + " |"
    sep = "|" + "---|" * (len(_COMPARISON_COLS) + 1)
    rows = [header, sep]
    for name, m in sorted(split.comparison.items()):
        cells = []
        for c in _COMPARISON_COLS:
            v = m.get(c, float("nan"))
            cells.append(f"{v:.4f}" if c not in ("auc", "n") else f"{v:.3f}")
        rows.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _split_section(split: SplitResult) -> str:
    s = split.shipped.metrics_calibrated
    u = split.shipped.metrics_uncalibrated
    return f"""### {split.model_id}

- Shots: **{split.n}**, base goal rate **{split.base_rate:.3f}**.
- Shipped model: calibrated logistic regression (standardization folded to raw
  coefficients; Platt-calibrated on out-of-fold predictions).
- Shipped calibration: slope **{s['cal_slope']:.3f}**, intercept
  **{s['cal_intercept']:.3f}** (target slope 0.9-1.1).
- Shipped discrimination: AUC **{s['auc']:.3f}**, log-loss **{s['log_loss']:.4f}**,
  Brier **{s['brier']:.4f}** (uncalibrated log-loss {u['log_loss']:.4f}).

Method comparison (grouped-by-match 5-fold CV, out-of-fold):

{_comparison_table(split)}
"""


def render_model_card(result: TrainResult) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"""# Model Card — Restart Lab xG v1 (`xg-header` + `xg-foot`)

*Generated {now} · engine `{ENGINE_VERSION}` · {ML_VERSION}*

## Model details
Two calibrated logistic expected-goals models — one for headers/non-foot first
contacts (`xg-header`), one for foot shots (`xg-foot`) — that score set-piece
shot contexts. Routed by body part at score time (`XGModelBundle`). Features are
closed-form geometry + freeze-frame traffic, identical at train and serve time
(`restart.engine.xg.shot_feature_vector`).

## Intended use
Score **simulated** corner/free-kick shot contexts inside the Restart Lab
engine, producing a per-shot P(goal) and a Monte Carlo `mean_xg`. Not a
play-by-play match xG product; not for betting.

## Training data
- Source: **StatsBomb Open Data** (non-commercial, attribution required).
- Corpus: real corner + free-kick shots from the configured competitions
  (`mart_setpiece_shots`), grouped by match for leakage-safe CV.
- Training-data hash: `{result.training_data_hash[:16]}…` (chains model to mart).
- The xG layer trains on **real data only** — never on simulator output
  (design doc 06 §1), so it remains the simulator's reality anchor.

## Metrics & calibration
The decision metric is calibration, not leaderboard AUC. The logistic baseline is
shipped (and keeps the simulation core dependency-free); gradient-boosted machines
are evaluated and reported below but not shipped.

{_split_section(result.header)}

{_split_section(result.foot)}

## Limitations
- Real-data xG conditions on real shot selection; simulated contexts can sit
  slightly off-manifold (doc 06 §2.3) — monitor feature overlap.
- Freeze-frame traffic features require freeze frames; shots without them are
  excluded from training (graceful degradation, doc 04 risk #1).
- Set-piece foot-shot samples are small; phases are encoded as features rather
  than sliced into separate models until learning curves justify it.
"""


def write_model_card(result: TrainResult, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_model_card(result), encoding="utf-8")
    return dest

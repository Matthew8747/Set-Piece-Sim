# Model Card - Restart Lab xG v1 (`xg-header` + `xg-foot`)

*Generated 2026-06-14 · engine `sim/0.4.0` · ml/0.1.0*

## Model details
Two calibrated logistic expected-goals models - one for headers/non-foot first
contacts (`xg-header`), one for foot shots (`xg-foot`) - that score set-piece
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
- Training-data hash: `e0917e4ad0409094…` (chains model to mart).
- The xG layer trains on **real data only** - never on simulator output
  (design doc 06 §1), so it remains the simulator's reality anchor.

## Metrics & calibration
The decision metric is calibration, not leaderboard AUC. The logistic baseline is
shipped (and keeps the simulation core dependency-free); gradient-boosted machines
are evaluated and reported below but not shipped.

### xg-header

- Shots: **298**, base goal rate **0.074**.
- Shipped model: calibrated logistic regression (standardization folded to raw
  coefficients; Platt-calibrated on out-of-fold predictions).
- Shipped calibration: slope **1.002**, intercept
  **0.004** (target slope 0.9-1.1).
- Shipped discrimination: AUC **0.658**, log-loss **0.2561**,
  Brier **0.0679** (uncalibrated log-loss 0.2737).

Method comparison (grouped-by-match 5-fold CV, out-of-fold):

| candidate | log_loss | brier | auc | cal_slope | cal_intercept | n |
|---|---|---|---|---|---|---|
| hist_gbm | 0.3596 | 0.0803 | 0.605 | 0.1729 | -1.8186 | 298.000 |
| lightgbm | 0.3586 | 0.0839 | 0.628 | 0.1715 | -1.8238 | 298.000 |
| logreg | 0.2737 | 0.0756 | 0.658 | 0.3904 | -1.4632 | 298.000 |
| random_forest | 0.2445 | 0.0658 | 0.709 | 0.7968 | -0.4358 | 298.000 |
| xgboost | 0.3431 | 0.0842 | 0.635 | 0.1963 | -1.7572 | 298.000 |


### xg-foot

- Shots: **677**, base goal rate **0.078**.
- Shipped model: calibrated logistic regression (standardization folded to raw
  coefficients; Platt-calibrated on out-of-fold predictions).
- Shipped calibration: slope **1.000**, intercept
  **0.002** (target slope 0.9-1.1).
- Shipped discrimination: AUC **0.790**, log-loss **0.2260**,
  Brier **0.0607** (uncalibrated log-loss 0.2297).

Method comparison (grouped-by-match 5-fold CV, out-of-fold):

| candidate | log_loss | brier | auc | cal_slope | cal_intercept | n |
|---|---|---|---|---|---|---|
| hist_gbm | 0.2851 | 0.0726 | 0.735 | 0.4226 | -1.0350 | 677.000 |
| lightgbm | 0.2782 | 0.0714 | 0.745 | 0.4534 | -0.9474 | 677.000 |
| logreg | 0.2297 | 0.0612 | 0.790 | 0.7620 | -0.4690 | 677.000 |
| random_forest | 0.2320 | 0.0623 | 0.798 | 0.8670 | -0.2588 | 677.000 |
| xgboost | 0.2885 | 0.0716 | 0.731 | 0.4205 | -1.0026 | 677.000 |


## Limitations
- Real-data xG conditions on real shot selection; simulated contexts can sit
  slightly off-manifold (doc 06 §2.3) - monitor feature overlap.
- Freeze-frame traffic features require freeze frames; shots without them are
  excluded from training (graceful degradation, doc 04 risk #1).
- Set-piece foot-shot samples are small; phases are encoded as features rather
  than sliced into separate models until learning curves justify it.

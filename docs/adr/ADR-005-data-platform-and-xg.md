# ADR-005 - Data platform & the xG ↔ engine integration

**Status:** Accepted · **Date:** 2026-06-14 · **Phase:** 4
**Related:** design doc 04 (data pipeline), design doc 06 (ML architecture), ADR-003 (engine),
ENGINE_VERSION `sim/0.4.0`

## Context

Phase 4 brings real data and the expected-goals layer. Three forces shape the design: the
**pure-domain rule** (`restart` imports no web/DB/ML), the **licensing reality** (no scraped
ratings; StatsBomb requires attribution and forbids raw redistribution), and the **circularity
trap** (xG must anchor the simulator to reality, so it must never train on simulator output).

## Decisions

1. **Two new packages, both outside the pure core.** `etl` (`restart_etl`) owns the raw → staging
   → marts lake and the `restart-etl` CLI; `ml` (`restart_ml`) owns xG training and the
   `restart-xg` CLI. The simulation core gains only a *pure* scoring contract (`restart.engine.xg`):
   `ShotContext`, the `XGScorer` protocol, a closed-form `LogisticXGScorer`, and `XGModelBundle`.
   No sklearn, no I/O in the core.

2. **CLI over orchestrator (doc 04 §4 challenged assumption).** A `restart-etl all` that rebuilds
   the world from raw in < 10 min is a better reproducibility story than Airflow/dbt/Dagster at
   this scale. Marts materialize as Parquet (the committed products) + a file-based **DuckDB**
   warehouse; a Postgres target is a drop-in later (tech-debt P4/6), so CI needs no DB server.

3. **One owned coordinate transform.** StatsBomb 120×80 → canonical 105×68 m (centre origin,
   attack L→R) lives in exactly one property-tested module. The same closed-form feature function
   (`shot_feature_vector`) builds both the training matrix and the engine's score-time features,
   so train and serve are the same quantities by construction.

4. **Mechanical licensing.** Every mart row carries a `source`; an approved allow-list is enforced
   by a gate (unit-tested in CI). Forbidden scraped-ratings sources (EA/sofifa) are named and
   rejected. Player attributes are **derived** with a documented method per value and tagged
   `{source, method, license}` - the licensing constraint becomes a credibility feature.

5. **xG models, and what ships.** Two body-part models (`xg-header`, `xg-foot`) - the reversible
   split from doc 06 §2.1. The full method comparison (LR vs HistGBM vs RandomForest vs XGBoost vs
   LightGBM) runs under **grouped-by-match CV**; the decision metric is **calibration**, not AUC.
   The **calibrated logistic ships** (slope ≈ 1.00 header & foot) because (a) it meets the
   acceptance target, (b) it serializes to plain coefficients the pure core can score, keeping the
   engine dependency-free, and (c) the marginally-higher-AUC random forest does not justify a
   framework dependency in the simulator. GBMs are evaluated and reported in the model card, not
   shipped. The shipped bundle is committed (`models/xg-v1.json`); CI cannot retrain (raw data is
   git-ignored), so the committed artifact is what the engine integration test exercises.

6. **Engine integration (G-14/G-15).** `SetPieceEngine` accepts an injected `XGScorer`. A shot
   emits a `ShotContext`; with a model wired, the goal/no-goal is a Bernoulli on the scored xG
   (so replay goals are xG-consistent), and the Monte Carlo report adds `mean_xg`/`n_xg_scored`.
   Without a model the engine keeps the Phase-2 placeholder (GK-save logit, G-9). The new path +
   `ShotEvent.xg` field bumps `ENGINE_VERSION` to `sim/0.4.0`.

## Consequences

- The core stays pure and the API runtime carries no ML framework (the backend reads the bundle
  JSON directly). Active-model pinning is a file pointer (`models/active.json`) until DB pinning
  lands.
- xG calibration is solved; the engine's **upstream** `[knob]`s (contest/delivery/traffic) remain
  uncalibrated, so the *distribution* of simulated contexts is not yet validated - the owed
  week-5 calibration task. Documented as the Phase-4 honesty note (assumptions G-14/G-15).
- Off-manifold risk (simulated contexts vs real-shot manifold) is registered (G-15, doc 06 §2.3);
  a population-stability check is the planned mitigation.

## Alternatives considered

- **Train xG on simulator output** - rejected: destroys the reality anchor (doc 06 §1).
- **Ship the GBM** - rejected for v1: pulls a non-pure dependency into scoring for a marginal,
  non-calibration gain; revisit if learning curves and calibration favor it.
- **Airflow/dbt now; Postgres now** - rejected: a CLI rebuild + file-based DuckDB beat an
  orchestrator and a server at this scale (doc 04 §4).
- **Scraped EA/sofifa ratings** - rejected outright (license-fatal for a public portfolio).

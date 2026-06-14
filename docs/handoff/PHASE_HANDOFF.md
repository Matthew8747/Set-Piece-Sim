# Phase Handoff

> Rewritten at the end of every completed phase.

## Last completed phase: Phase 4 — Data platform, player profiles & xG v1 (`sim/0.4.0`)

### What shipped
- **`etl` (`restart_etl`, CLI `restart-etl`)** — pure-data raw→staging→marts pipeline.
  `fetch statsbomb` (byte-exact cache + manifest, git-ignored), `stage` (one owned 105×68 m
  coordinate transform, property-tested; typed Parquet), `marts` (+ file-based DuckDB), `gates`
  (mechanical license + distribution), `all`. Built on **real StatsBomb WC2022 + Euro2024**:
  975 corner/FK shots (75 goals), 1,259 players.
- **Marts:** `mart_setpiece_shots` (xG training table, freeze-frame traffic features),
  `mart_calibration_targets`, `mart_players`, `mart_player_attributes` (12 derived,
  provenance-tagged `{source, method, license}` attributes — aerial-derived heading,
  set-piece-completion-derived delivery, literature/curated priors otherwise; bounds-clamped),
  `mart_defensive_schemes`.
- **`ml` (`restart_ml`, CLI `restart-xg`)** — System A xG on **real data only**. `xg-header` +
  `xg-foot` calibrated logistic models; full method comparison (LR/HistGBM/RF/XGBoost/LightGBM)
  under grouped-by-match CV; Platt calibration on OOF; MLflow (sqlite); generated model card.
  Shipped logistic calibration slope ≈ **1.00** (both splits).
- **Engine (pure):** `restart.engine.xg` (`ShotContext`, `XGScorer`, `LogisticXGScorer`,
  `XGModelBundle`). `SetPieceEngine(xg_scorer=…)` scores shots → Bernoulli on real-data xG
  (G-14/G-15). `ENGINE_VERSION` → `sim/0.4.0`; `ShotEvent.xg` added.
- **API:** Monte Carlo report carries `mean_xg`/`n_xg_scored`/`xg_model`; backend loads the
  committed `models/xg-v1.json` directly (no ML dep in the API runtime). shared-types updated.
- Details: [CHANGELOG](../../CHANGELOG.md) Phase-4 entry; [ADR-005](../adr/ADR-005-data-platform-and-xg.md).

### Validation evidence
All gates green (ruff, black, mypy --strict, pytest, next build, eslint, tsc, prettier, vitest).
`restart-etl gates` → `== gates PASS ==` (license: all sources approved; coords on-pitch;
goal rate 0.077 in band). `restart-xg train` → shipped logistic `cal_slope` 1.002 (header) /
1.000 (foot). API acceptance: `montecarlo` returns `mean_xg > 0`, `xg_model="xg-v1"`.

### Debugging history worth knowing (saves future sessions time)
1. **Pure-domain vs ML.** The core must not import sklearn. Resolution: the LR model serializes
   to plain coefficients consumed by a pure `LogisticXGScorer`; GBMs (if ever shipped) inject via
   the `XGScorer` protocol from the adapter. The backend reads the bundle JSON directly — no
   `restart_ml` import in the API.
2. **Committed model, git-ignored data.** CI can't retrain (raw data git-ignored, 347 MB), so the
   small derived bundle is committed under `models/` (`.gitignore` re-includes `models/*.json`);
   the engine↔model integration test runs against it.
3. **mypy + data libs.** pandas avoided (its inline types fight `--strict`); pyarrow/duckdb/sklearn
   etc. are `ignore_missing_imports` overrides; a few targeted `type: ignore[no-untyped-call]` on
   pyarrow read/write. Use `dict[str, Any]` for mart rows so `int()/float()` calls typecheck.
4. **MLflow file store is deprecated/maintenance-mode** and raises; switched to a local
   `sqlite:///data/mlflow.db` backend.

### Open decisions carried forward
- xG mapping is calibrated; the engine's **upstream** `[knob]`s are not, so the simulated
  shot-context *distribution* is unvalidated — the owed week-5 calibration gate (now with real
  base rates in `mart_calibration_targets` to fit against).
- Off-manifold risk (G-15): population-stability check of simulated vs training feature
  distributions is the planned mitigation.
- Player attributes are derived but **not yet wired into the API squads** (still demo squads);
  squad selection from `mart_players`/attributes is API/persistence work scoped to Phase 6.

## Next phase: Phase 5 — Optimization engine (roadmap weeks 7–8)

Scope: System B — Optuna TPE over the Routine Spec sub-space; random-search baseline at equal
budget; screen-then-confirm (500-sim screen → top-k confirm at 10k with common random numbers);
anti-exploit flagging; study persistence; LightGBM surrogate + SHAP "insights"; the canonical
*England corners vs Argentina zonal* study; attribute sensitivity analysis (doc 04 §3 guardrail).
Objective = `mean_xg` (now produced by the real-data model) with counterattack risk reported.

### Risks for Phase 5
1. Throughput: the reference engine is ≈ 3 sims/s — 10⁵–10⁶-sim studies need the fused Numba
   scenario kernel (ADR-003 d8) first, or studies will be painfully slow.
2. Optimizer exploits sim artifacts → anti-exploit rules + face-validity review of the top-k.
3. TPE may underperform on the categorical-heavy space → the random-search baseline catches this
   honestly.
4. Attribute priors dominating rankings → the scheduled ±10% sensitivity analysis decides whether
   to report routine *classes* vs player-precise prescriptions.

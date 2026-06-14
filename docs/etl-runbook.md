# Runbook — Data platform & xG (Phase 4)

Rebuild every Phase-4 number from a clean clone. The raw cache and marts are
git-ignored (StatsBomb license + size); the trained xG coefficient bundle
(`models/xg-v1.json`) **is** committed, so the engine ships a working model
without retraining.

## Prerequisites
- `uv sync --all-packages` (installs `restart_etl`, `restart_ml`, and the ML stack).
- Network access to `raw.githubusercontent.com/statsbomb/open-data` for the fetch.

## 1. Build the data lake (`restart-etl`)

```bash
# Full rebuild (fetch -> stage -> marts -> gates). Target < 10 min on the corpus.
uv run restart-etl all --competitions wc2022,euro2024

# …or step by step:
uv run restart-etl fetch statsbomb --competitions wc2022,euro2024  # -> data/raw (git-ignored)
uv run restart-etl stage                                           # -> data/staging/*.parquet
uv run restart-etl marts                                           # -> data/marts/*.parquet + DuckDB
uv run restart-etl gates                                           # license + distribution checks
```

Outputs (all git-ignored under `data/`):
- `data/raw/statsbomb/…` byte-exact JSON + `manifest.json` (url, sha256, fetched_at, license).
- `data/staging/setpiece_shots.parquet` typed, coordinate-standardized.
- `data/marts/mart_*.parquet` + `data/marts/restart.duckdb` warehouse.

`gates` must end `== gates PASS ==`. License violations and impossible data are **FAIL**
(build-red); distribution drift is **FLAG** (surfaced, non-fatal).

## 2. Train the xG models (`restart-xg`)

```bash
# Trains xg-header + xg-foot on data/marts/mart_setpiece_shots.parquet (REAL data only),
# runs the grouped-CV method comparison, calibrates, writes the bundle + model card,
# and logs runs to MLflow (sqlite:///data/mlflow.db).
uv run restart-xg train

# Reproduce only the model card (no MLflow):
uv run restart-xg card
```

Outputs:
- `models/xg-v1.json` (committed) + `models/active.json` pointer.
- `docs/model-cards/xg-v1.md` (committed).
- `data/mlflow.db` (git-ignored). Browse with `uv run mlflow ui --backend-store-uri sqlite:///data/mlflow.db`.

Acceptance: the shipped logistic calibration slope is 0.9–1.1 (printed as `shipped logistic:
cal_slope=…`).

## 3. Verify the engine scores with the real model

The backend auto-loads `models/active.json` and injects the scorer. A Monte Carlo
response then carries `mean_xg`, `n_xg_scored`, and `xg_model: "xg-v1"`:

```bash
uv run uvicorn restart_api.main:app --app-dir apps/backend/src
# POST /api/v1/setpieces/montecarlo {routine_id, scheme_id, n_sims} -> body.mean_xg > 0
```

## Notes
- CI does not fetch raw data (git-ignored). The mechanical license + quality gate **logic**
  is unit-tested (`test_etl_gates.py`), and the engine↔model integration runs against the
  committed bundle (`test_setpieces.py::test_montecarlo_reports_real_data_xg`).
- xG trains on **real data only** — never on simulator output (design doc 06 §1).

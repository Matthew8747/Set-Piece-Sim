# Project Status

> Update this file at the end of every phase. Keep it under one screen.

| Field | Value |
|---|---|
| **Current phase** | Phase 4 complete — data platform + player profiles + xG v1. Next: Phase 5 (optimizer) |
| **Completed phases** | Design · P0 foundation · P1 physics (`sim/0.1.0`) · P2 agents & engine (`sim/0.2.0`) · P3 Monte Carlo + MVP (`sim/0.3.0`) · P4 data + xG (`sim/0.4.0`) |
| **Current branch** | `feat/phase4-data-xg` (PR open → `main`) |
| **Latest main commit** | `ad1524b` Phase 3 line (P2/P3/P4 stacked on the feature branches) |
| **Engine version** | `sim/0.4.0` |
| **Test count** | ~440 (Python across core/etl/ml/backend + 3 frontend) · mypy strict clean · ruff/black/eslint/tsc/prettier clean |

## What works end-to-end now (the MVP + real xG)

`uv run uvicorn restart_api.main:app --app-dir apps/backend/src` + `npm run dev -w apps/frontend`
→ open `/workbench` → select corner routine + defensive scheme → "Simulate one" (animated SVG
replay + event timeline, per-shot xG) or "Run 200×" (Wilson-CI table + `mean_xg` from the
real-data model). The backend auto-loads the committed `models/xg-v1.json`. Demo squads only.

Data + models: `uv run restart-etl all` (StatsBomb WC2022+Euro2024 → 975 set-piece shots,
1,259 players, gates PASS); `uv run restart-xg train` (xg-header + xg-foot, shipped logistic
calibration slope ≈ 1.00). See [docs/etl-runbook.md](../etl-runbook.md).

## Active / upcoming milestones

- **Phase 5 (roadmap weeks 7–8):** Optuna TPE optimizer over the Routine Spec sub-space,
  random-search baseline, screen-then-confirm, SHAP insights, attribute sensitivity analysis.
- **Calibration (roadmap week 5 gate, still owed):** engine *upstream* `[knob]`s
  (contest/delivery/traffic) vs real base rates — xG mapping is calibrated, but the simulated
  shot-context *distribution* is not yet validated. Goal rate ~5% sim vs 2–3% real.
- **Throughput follow-up:** fused Numba scenario kernel (ADR-003 d8) for 100k-sim batches (needed
  before Phase-5 optimization studies; reference engine ≈ 3 sims/s).

## Known blockers

- None blocking. Sub-agent dispatch was available this phase but Phase 4 was built inline (the
  data-contract-defining work was tightly sequential); future phases can parallelize disjoint
  packages.

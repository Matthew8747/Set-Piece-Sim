# Project Status

> Update this file at the end of every phase. Keep it under one screen.

| Field | Value |
|---|---|
| **Current phase** | Phase 5 complete — routine optimizer (System B). Next: Phase 6 (API & Scenario Workbench) |
| **Completed phases** | Design · P0 foundation · P1 physics (`sim/0.1.0`) · P2 agents & engine (`sim/0.2.0`) · P3 Monte Carlo + MVP (`sim/0.3.0`) · P4 data + xG (`sim/0.4.0`) · P5 optimizer (`restart_opt 0.1.0`) |
| **Current branch** | `feat/phase5-optimizer` (PR open → `main`) |
| **Latest main commit** | `bede0b9` (origin/main = P3 merge); P4/P5 stacked on the feature branches |
| **Engine version** | `sim/0.4.0` (unchanged in P5 — the optimizer does not touch engine physics) |
| **Test count** | ~490 (Python across core/etl/ml/optimizer/backend + 3 frontend) · mypy strict clean · ruff/black/eslint/tsc/prettier clean |

## What works end-to-end now (the MVP + real xG)

`uv run uvicorn restart_api.main:app --app-dir apps/backend/src` + `npm run dev -w apps/frontend`
→ open `/workbench` → select corner routine + defensive scheme → "Simulate one" (animated SVG
replay + event timeline, per-shot xG) or "Run 200×" (Wilson-CI table + `mean_xg` from the
real-data model). The backend auto-loads the committed `models/xg-v1.json`. Demo squads only.

Data + models: `uv run restart-etl all` (StatsBomb WC2022+Euro2024 → 975 set-piece shots,
1,259 players, gates PASS); `uv run restart-xg train` (xg-header + xg-foot, shipped logistic
calibration slope ≈ 1.00). See [docs/etl-runbook.md](../etl-runbook.md).

## What's new in Phase 5 (the optimizer)

`restart-opt canonical` runs the *England corners vs Argentina zonal* study end-to-end: Optuna TPE
screen + equal-budget random baseline → top-k confirmed at a larger budget under common random
numbers → winner vs library baseline by non-overlapping 95% CIs → anti-exploit + face-validity
review → LightGBM+SHAP insights → ±10% attribute sensitivity verdict. Pure pieces live in
`restart.optimize` (genome/objective/confirm/guards); all Optuna/LightGBM/SHAP/MLflow + IO live in
the new `restart_opt` package. Studies persist to `optimization_studies/` and log to MLflow.

## Active / upcoming milestones

- **Phase 6 (roadmap weeks 9–10):** FastAPI surface, Arq worker + progress, Scenario Workbench,
  squad selection from `mart_players`/attributes (replaces demo squads), optimization UI later (P7).
- **Calibration (roadmap week 5 gate, still owed):** engine *upstream* `[knob]`s
  (contest/delivery/traffic) vs real base rates — xG mapping is calibrated, but the simulated
  shot-context *distribution* is not yet validated. Goal rate ~5% sim vs 2–3% real.
- **Throughput follow-up (🔴 carried forward):** fused Numba scenario kernel (ADR-003 d8) for
  10⁵–10⁶-sim batches. Reference engine ≈ 3 sims/s (measured) — P5 studies run at a scoped,
  documented budget because the kernel is deferred (ADR-006).

## Known blockers

- None blocking. Phase 5 was built inline (determinism-sensitive, tightly coupled optimizer code);
  the carried-forward kernel is what gates *large* studies, not correctness.

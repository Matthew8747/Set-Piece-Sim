# Project Status

> Update this file at the end of every phase. Keep it under one screen.

| Field | Value |
|---|---|
| **Current phase** | Phase 7 complete — Optimization UI & 3D replay. Next: Phase 8 (scenario realism — wider attacker template, defensive structure, genome variance) |
| **Completed phases** | Design · P0 foundation · P1 physics (`sim/0.1.0`) · P2 agents & engine (`sim/0.2.0`) · P3 Monte Carlo + MVP (`sim/0.3.0`) · P4 data + xG (`sim/0.4.0`) · P5 optimizer (`restart_opt 0.1.0`) · P6 API & Workbench (`restart_api`, `@restart/pitch-kit`) · P7 Optimization UI & 3D replay |
| **Current branch** | `feat/phase7-optimization-ui` (PR → `main`) |
| **Latest main commit** | `dd29ce4` (origin/main = P6 merge); P7 branched off it |
| **Engine version** | `sim/0.4.0` (unchanged in P7 — the read-API/UI phase touches no engine physics; Phase 8 will bump it) |
| **Test count** | ~535+ (Python across core/etl/ml/optimizer/backend + frontend vitest 24 + pitch-kit 20 + Playwright journey) · mypy strict clean · ruff/black/eslint/tsc/prettier clean · OpenAPI drift gate green |

## What works end-to-end now (the Scenario Workbench, real squads)

`uv run uvicorn restart_api.main:app --app-dir apps/backend/src` + `npm run dev -w @restart/frontend`
→ open `/scenarios` → "New scenario" (canonical WC2026 corner) → **Build** (real-squad pickers from
the marts + routine/scheme) → **Simulate** (async sim-run, polled progress, xG distributions +
KPI/CI cards, determinism banner) → **Replay** (worst/median/best single-sim trajectory). The
backend auto-loads the committed `models/xg-v1.json`. Server-free by default (SQLite + in-process
queue); Postgres + Arq are config-selected drop-ins. The 3-minute journey is covered by a Playwright
E2E at a reduced budget (`n_sims=24`).

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

- **Phase 8 (next — scenario realism):** widen the corner genome (O-2) — more attacker slots (4→7+)
  with off-ball / non-box roles, structured defensive defaults (near-post man, line), wider
  delivery/run variance — to fix the "too many defenders, too few attackers" imbalance and the
  low-variance replay look. Bumps `ENGINE_VERSION` (first engine change since P4). Later engine
  phases: free kicks (offside, off-ball runners), evolutionary search (GA + lineage viz, gated on the
  🔴 kernel).
- **Phase 7 (done):** optimization UI (convergence, parallel-coords, top-k vs baseline, SHAP
  insights), workbench CRN compare mode, on-demand 3D replay. Team-intelligence (`/teams`) +
  report-export deferred to Phase 7.x (doc 07 IA).
- **Calibration (roadmap week 5 gate, still owed):** engine *upstream* `[knob]`s
  (contest/delivery/traffic) vs real base rates — xG mapping is calibrated, but the simulated
  shot-context *distribution* is not yet validated. Goal rate ~5% sim vs 2–3% real.
- **Throughput follow-up (🔴 carried forward):** fused Numba scenario kernel (ADR-003 d8) for
  10⁵–10⁶-sim batches. Reference engine ≈ 3 sims/s (measured) — P5 studies run at a scoped,
  documented budget because the kernel is deferred (ADR-006).

## Known blockers

- None blocking. Phase 5 was built inline (determinism-sensitive, tightly coupled optimizer code);
  the carried-forward kernel is what gates *large* studies, not correctness.

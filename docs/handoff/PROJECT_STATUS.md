# Project Status

> Update this file at the end of every phase. Keep it under one screen.

| Field | Value |
|---|---|
| **Current phase** | Phase 9 — Evolutionary routine search (NSGA-II GA + CMA-ES). Built on P8. Next: Phase 10 (throughput — Numba scenario kernel) |
| **Completed phases** | Design · P0–P6 · P7 Optimization UI & 3D replay (PR #7) · P8 Scenario realism (`sim/0.5.0`, PR #8) · P9 Evolutionary search (`restart_opt`) |
| **Current branch** | `feat/phase9-evolution` (off `feat/phase8-scenario-realism`; PR → `main`) |
| **Latest main commit** | `dd29ce4` (origin/main = P6 merge); P7 (PR #7) + P8 (PR #8) branch off main; P9 stacks on P8 |
| **Engine version** | `sim/0.5.0` (unchanged in P9 — optimizer-only; the engine was bumped in P8) |
| **Test count** | ~555 (Python across core/etl/ml/optimizer/backend + frontend/pitch-kit vitest + Playwright) · mypy strict clean · ruff/black/eslint/tsc/prettier clean · OpenAPI drift gate green |

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

- **Phase 9 (current — done):** evolutionary routine search — NSGA-II genetic algorithm (full mixed
  genome) + CMA-ES, behind the existing sampler dispatch; the canonical study runs TPE vs random vs
  evolution at equal budget with per-trial generation lineage. See
  [ADR-010](../adr/ADR-010-evolutionary-search.md).
- **Phase 8 (done, PR #8):** scenario realism — 7-attacker template, basic free kicks, `near_post_man`
  defence; `ENGINE_VERSION` `sim/0.5.0`. **Phase 7 (PR #7):** optimization UI + CRN compare + 3D replay.
- **Phase 10 (next — 🔴 throughput):** fused Numba scenario kernel (ADR-003 d8) — scales evolution
  (bigger populations / more generations) + unlocks 10⁵–10⁶-sim studies. Reference engine ≈ 3 sims/s;
  studies run at a scoped budget until it lands ([roadmap](../ROADMAP-future-enhancements.md) §1).
- **Calibration (🔴 owed):** fit the engine `[knob]`s to real base rates (goal ~5% sim vs 2–3% real)
  — roadmap §2 (simulation-based inference).

## Known blockers

- None blocking. Phase 5 was built inline (determinism-sensitive, tightly coupled optimizer code);
  the carried-forward kernel is what gates *large* studies, not correctness.

# Project Status

> Update this file at the end of every phase. Keep it under one screen.

| Field | Value |
|---|---|
| **Current phase** | Phase 8 — Scenario realism (engine `sim/0.5.0`). Phase 7 (optimization UI / 3D replay) ships in parallel PR #7. Next: Phase 9 (throughput — Numba scenario kernel) |
| **Completed phases** | Design · P0 foundation · P1 physics (`sim/0.1.0`) · P2 agents & engine (`sim/0.2.0`) · P3 Monte Carlo + MVP (`sim/0.3.0`) · P4 data + xG (`sim/0.4.0`) · P5 optimizer (`restart_opt 0.1.0`) · P6 API & Workbench (`restart_api`, `@restart/pitch-kit`) · P7 Optimization UI & 3D replay (PR #7) · P8 Scenario realism (`sim/0.5.0`) |
| **Current branch** | `feat/phase8-scenario-realism` (off `main` @ `dd29ce4`; PR → `main`) |
| **Latest main commit** | `dd29ce4` (origin/main = P6 merge); P7 (PR #7) + P8 are independent branches off it |
| **Engine version** | `sim/0.5.0` (**bumped in P8** — the corner template now places up to 7 attackers with off-ball roles + basic free kicks, changing simulated context for a given routine) |
| **Test count** | ~540 (Python across core/etl/ml/optimizer/backend + frontend/pitch-kit vitest + Playwright) · mypy strict clean · ruff/black/eslint/tsc/prettier clean · OpenAPI drift gate green |

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

- **Phase 8 (current — done):** scenario realism — 7-attacker corner template with off-ball zones,
  basic free-kick genome, structured `near_post_man` defence; `ENGINE_VERSION` `sim/0.5.0`; canonical
  study re-baselined. See [ADR-009](../adr/ADR-009-scenario-realism.md).
- **Phase 7 (parallel PR #7):** optimization UI (convergence, parallel-coords, top-k, SHAP insights),
  workbench CRN compare, on-demand 3D replay. Independent branch off the same `main`.
- **Phase 9 (next — 🔴 throughput):** fused Numba scenario kernel (ADR-003 d8) for 10⁵–10⁶-sim batches.
  Reference engine ≈ 3 sims/s (slower with 7 attackers) — studies run at a scoped, documented budget
  until the kernel lands (ADR-006). The keystone dependency for everything below
  ([roadmap](../ROADMAP-future-enhancements.md) §1).
- **Calibration (🔴 owed):** fit the engine `[knob]`s to real base rates (goal ~5% sim vs 2–3% real)
  — roadmap §2 (simulation-based inference).

## Known blockers

- None blocking. Phase 5 was built inline (determinism-sensitive, tightly coupled optimizer code);
  the carried-forward kernel is what gates *large* studies, not correctness.

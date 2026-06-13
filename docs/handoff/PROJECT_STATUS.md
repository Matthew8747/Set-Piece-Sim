# Project Status

> Update this file at the end of every phase. Keep it under one screen.

| Field | Value |
|---|---|
| **Current phase** | Phase 3 complete — Monte Carlo + analytics + MVP. Next: Phase 4 (data + xG) |
| **Completed phases** | Design · P0 foundation · P1 ball physics (`sim/0.1.0`) · P2 agents & engine (`sim/0.2.0`) · P3 Monte Carlo + MVP (`sim/0.3.0`) |
| **Current branch** | `feat/phase3-montecarlo-mvp` (PR open → `main`) |
| **Latest main commit** | `0cd57c3` Phase 2 (P3 in PR #3); P2 = PR #2 |
| **Engine version** | `sim/0.3.0` |
| **Test count** | 413 (410 Python + 3 frontend) · mypy strict clean · ruff/black/eslint/tsc/prettier clean |

## What works end-to-end now (the MVP)

`uv run uvicorn restart_api.main:app --app-dir apps/backend/src` + `npm run dev -w apps/frontend`
→ open `/workbench` → select corner routine + defensive scheme → "Simulate one" (animated SVG
replay + event timeline) or "Run 200×" (Wilson-CI probability table). Demo squads only.

## Active / upcoming milestones

- **Phase 4 (roadmap week 6):** ETL (StatsBomb → marts), real player profiles, xG v1, MLflow.
- **Calibration (roadmap week 5 gate, still owed):** all `EngineConfig`/physics `[knob]`
  params vs real corner base rates. Goal rate ~5% sim vs 2–3% real — uncalibrated by design.
- **Throughput follow-up:** fused Numba scenario kernel (ADR-003 d8) for 100k-sim batches; the
  reference engine is ~3 sims/s, fine for the MVP but not for Phase-5 optimization studies.

## Known blockers

- Claude **sub-agent dispatch unavailable** (monthly spend limit) — all Phase 2/3 implementation
  done inline on the lead session. Re-enable to parallelize Phase 4.

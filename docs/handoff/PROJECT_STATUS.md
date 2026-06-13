# Project Status

> Update this file at the end of every phase. Keep it under one screen.

| Field | Value |
|---|---|
| **Current phase** | Phase 3 — Monte Carlo + analytics + MVP integration (starting) |
| **Completed phases** | Design package · P0 foundation · P1 ball physics (`sim/0.1.0`) · P2 agents & tactical engine (`sim/0.2.0`) |
| **Current branch** | `feat/phase2-agents-tactics` (PR open → `main`); Phase 3 branches from it |
| **Latest main commit** | `47d4af5` — Phase 1 (Phase 2 in PR) |
| **Engine version** | `sim/0.2.0` |
| **Test count** | 251 (all green) · mypy strict clean · ruff/black clean |

## Active milestones (roadmap week 5 + MVP pull-forward)

- Phase 3: Monte Carlo batch runner (seeded Philox streams, parallel where useful), outcome
  metrics with Wilson/bootstrap CIs, simulation reports, optimization *interfaces only*
  (Optuna/BO/evolutionary-ready), plus MVP vertical slice: API endpoints + Scenario Workbench
  frontend (routine selector → run batch → results panel + event timeline + pitch view).
- Calibration of [knob] parameters remains Phase-3's credibility gate (after MC machinery).

## Upcoming milestones

- Phase 4: ETL + real player profiles + xG v1. Phase 5: Bayesian optimization studies.

## Known blockers

- Claude sub-agent dispatch unavailable this billing period (spend limit) — implementation
  continues inline on the lead session.
- Engine outcome rates uncalibrated by design until the Phase-3 harness exists.

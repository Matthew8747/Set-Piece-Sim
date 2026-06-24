# Architecture Summary

Canonical source: [docs/02-system-architecture.md](../02-system-architecture.md). This is the
5-minute orientation; trust the canonical doc on conflict.

## System in one paragraph

A **modular monolith**: a pure-Python simulation core (`packages/simulation-core`, import name
`restart`) wrapped by a FastAPI adapter (`apps/backend`, `restart_api`) and a queue worker
(Arq/Redis, Phase 6), persisting entities/summaries to Postgres and bulk per-sim event logs to
Parquet (DuckDB for analytics). A Next.js 16 frontend (`apps/frontend`) consumes the REST API;
TS contract types live in `packages/shared-types`. Everything heavy runs in the core; the web
layer translates DTOs.

## Layering (the dependency rule)

```
restart.domain  ← restart.physics ← restart.{agents,tactics,engine}   (pure, no I/O)
        ↑ ports implemented by storage/ (Phase 4+)
restart_api / worker  (adapters; import restart, never the reverse)
apps/frontend → REST → restart_api
```

## Key decisions (details in ADRs / design docs)

- **Throughput architecture:** SoA `(n_sims, …)` tensors; fused Numba kernels as production
  batch paths *adopted on measurement*, with NumPy references retained as equivalence-tested
  oracles (ADR-001 + addendum, ADR-002). Per-core budget: ≥500 corner sims/s (design doc 05).
- **Determinism:** fixed-step RK4 (dt 5 ms); Philox/SeedSequence RNG streams; `ENGINE_VERSION`
  stamped on every result; scenario-hash idempotency (DB design, doc 03).
- **Two ML systems, never conflated** (doc 06): xG trained on real StatsBomb data (reality
  anchor) vs routine search driven by the simulator (Optuna TPE primary, Phase 5).
- **Routine Spec** (`rs/1.0`, JSONB document): simultaneously the UI builder format, the
  optimizer genome, and the replay metadata; compiled to array-form `SimProgram` for execution.
- **Data:** raw→staging→marts lake under `data/` (git-ignored); license gate is mechanical
  (CI), StatsBomb-primary, derived provenance-tagged attributes (doc 04).

## Rejected alternatives (with one-line reasons)

Microservices (solo build, demo fragility) · PyBullet/Pymunk (no aerodynamics / 2D) · JAX v1
(Windows friction, unused gradients) · all-results-in-Postgres (bulk logs → Parquet) ·
Airflow/dbt now (a CLI rebuild beats an orchestrator at this scale) · RL for routine discovery
v1 (one-shot design problem; Tier-3 research note).

## Dependency map (runtime)

| Package | Depends on |
|---|---|
| `restart` (simulation-core) | numpy, scipy (oracle/stats incl. Wilson CIs), numba (JIT kernels), pydantic (config) |
| `restart_etl` (etl) | httpx, pyarrow, duckdb, numpy, pydantic - **pure data**, no `restart` import on the fetch/staging path |
| `restart_ml` (ml) | scikit-learn, xgboost, lightgbm, mlflow, pyarrow, **restart** (xG feature/scorer contract), **restart_etl** (mart readers) |
| `restart_api` (backend) | fastapi, uvicorn, pydantic-settings, **restart** (engine + montecarlo + xg); loads the committed xG bundle JSON directly (no ML dep) |
| `apps/frontend` | next 16, react 19, tailwind v4, **@restart/shared-types** (fetches restart_api) |

Subpackage map (as built, P4): `restart.{domain, physics, simulation, players, agents,
tactics, engine, montecarlo, optimize}`; `restart.engine.xg` is the pure xG scoring contract.
Layer order: domain ← physics ← simulation/players ← agents/tactics ← engine ← montecarlo ←
optimize. `optimize` has interfaces only (Phase 5 fills). New Phase-4 packages outside the core:
`restart_etl` (data lake + CLI) and `restart_ml` (xG training + CLI); both adapter-tier, neither
is imported by `restart`. The shipped xG bundle is committed under `models/`.
| Dev gates | ruff, black, mypy(strict), pytest(+benchmark), hypothesis, eslint, prettier, vitest |
| Phase 4+ (planned) | SQLAlchemy/Alembic, Arq+Redis, Postgres, DuckDB, MLflow, Optuna, cmaes |

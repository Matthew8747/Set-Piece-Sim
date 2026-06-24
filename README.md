# Restart Lab

**Find the highest-value way to take a corner or a free kick.**

Restart Lab plays a set piece out thousands of times in a physics engine, scores every chance it
creates with a real-data expected-goals model, then searches for the routine that works best against a
specific defence. It is an analyst's console, built around the 2026 World Cup.

> Status: the platform is feature-complete and runs end-to-end. The current work in progress is a
> Numba throughput kernel (an internal speed-up, not a blocker). See [Roadmap](#roadmap).

## What it does

The product is one loop, three steps.

| | Step | What happens |
|---|---|---|
| **Simulate** | Play the set piece out | A deterministic engine flies the ball with real spin, drag and bounce, moves every attacker and defender, and resolves the delivery into a shot, a clearance or a scramble. |
| **Measure** | Score it with real xG | Each simulated chance is graded by an expected-goals model trained on real World Cup and Euros data (StatsBomb open data), reported with confidence intervals so noise never reads as a result. |
| **Optimise** | Search for the best routine | An optimizer tunes the delivery, the runs and the timing across thousands of trials. Any routine it proposes has to beat random search before it counts. |

There are two consoles:

- **Scenario Workbench** (`/scenarios`): build a set piece from real squads, simulate it, watch the 2D
  and 3D replay, and compare two routines under common random numbers.
- **Optimization studies** (`/optimize`): read a completed routine search. Convergence, a
  parallel-coordinates view of every trial, the SHAP explanation of what made the winners win, and an
  honesty banner that refuses to call something a winner unless the statistics back it.

## Why it is interesting

The engineering decisions are the point, not the football. A few that hold the project together:

- **An honest optimizer.** Every search runs an equal-budget random baseline. A routine is never
  reported as a winner unless its confidence interval clears the baseline's. An optimizer that cannot
  beat random search at equal budget is theatre, and the UI says so out loud.
- **Reproducibility as a feature.** Every persisted result carries the engine build id
  (`ENGINE_VERSION`). The same scenario compiles to a byte-identical program, and the same seed
  produces a byte-identical result, independent of batch size. Anything physics-affecting bumps the
  version so stale results are detectable rather than silent.
- **A pure simulation core.** The `restart` package imports no web, database, ML or IO code. Every
  adapter (the API, the optimizer driver, the ETL) depends inward on the core, never the reverse, so
  the simulator stays a small, deterministic, testable library.
- **A verified speed-up.** The throughput kernel is a Numba port of the engine, checked to `1e-9`
  against the readable NumPy reference, the same discipline used for the physics formulas. The
  randomness is externalized so the fast path and the reference produce identical draws.
- **Provenance, not scraped ratings.** No proprietary player ratings are used. Every attribute is
  derived from open event data and tagged with where it came from.

## Quickstart

Prerequisites: [uv](https://docs.astral.sh/uv/) 0.5+ and Node.js 24+. uv provisions Python 3.12 for
you.

```bash
git clone <repo-url> && cd Set-Piece-Sim
cp .env.example .env            # local config; never commit .env

uv sync --all-packages          # Python workspace (backend + simulation core)
npm install                     # TypeScript workspace (frontend + shared types)
uv run pre-commit install       # git hooks

# Run everything CI runs:
./scripts/verify.sh             # or: powershell -File scripts/verify.ps1

# Dev servers:
uv run uvicorn restart_api.main:app --reload --app-dir apps/backend/src   # API on :8000
npm run dev -w apps/frontend                                              # web on :3000
```

The API boots server-free: with no database configured it uses a local SQLite store and an in-process
job queue, so nothing external is required. The `/optimize` pages work immediately from the committed
study. The `/scenarios` squads need the marts, built locally by the StatsBomb ETL
([etl-runbook.md](docs/etl-runbook.md)).

Full guides: [setup](docs/setup-guide.md), [development](docs/development-guide.md),
[contributing](CONTRIBUTING.md).

## Architecture

```
apps/
  backend/      FastAPI application (restart_api): web adapter, no domain logic
  frontend/     Next.js 16 app (TypeScript, Tailwind v4, React Three Fiber for 3D)
packages/
  simulation-core/  Pure-domain Python package (restart): physics, agents, tactics, Monte Carlo
  etl/ ml/ optimizer/   StatsBomb ETL, the xG model, and the routine optimizer (offline, out of the API)
  shared-types/     TypeScript types generated from the API's OpenAPI schema (drift-gated in CI)
  pitch-kit/        Shared SVG pitch and chart primitives
docs/           design package, ADRs, and living guides
infra/          docker-compose (Postgres + Redis) for the scaled path
scripts/        verify.{sh,ps1}: the full CI suite, locally
```

## Deploying

Recommended stack: **Fly.io** (backend), **Vercel** (frontend), **Neon** (Postgres, only when scaling
past the server-free default). The backend is a standard container and runs anywhere (Render, Railway,
Cloud Run). A full runbook, including whether to host at all, is in [docs/GO-LIVE.md](docs/GO-LIVE.md).

A [`fly.toml`](fly.toml) and a lean [backend Dockerfile](apps/backend/Dockerfile) (backend plus
simulation core only, no optimizer or ML stack) are provided:

```bash
fly launch --no-deploy                                    # create the app (edit the name in fly.toml)
fly volumes create restart_data --size 1 --region lhr     # persists the marts + SQLite store
fly secrets set RESTART_CORS_ORIGINS='["https://YOUR-APP.vercel.app"]'
fly deploy
```

The frontend deploys to Vercel with zero config: set the project root directory to `apps/frontend` and
`NEXT_PUBLIC_API_BASE_URL` to the backend URL. Liveness and readiness are at `/healthz` and `/readyz`.

## Key design decisions

The short answers to "why did you build it this way?", each with its source.

| Decision | Rationale | Source |
|---|---|---|
| Pure-domain core (`restart` imports no web, DB, ML or IO) | The simulator stays a testable, deterministic library; every adapter depends inward, never the reverse | [ADR-005](docs/adr/ADR-005-data-platform-and-xg.md), [ADR-006](docs/adr/ADR-006-routine-optimizer.md) |
| `ENGINE_VERSION` and determinism | Reproducibility is a product feature; physics-affecting changes bump the version so stale results are detectable | [ADR-009](docs/adr/ADR-009-scenario-realism.md) |
| Mandatory random baseline | A search that cannot beat random at equal budget is theatre, and a "winner" without a significant interval is a deception trap | [doc 09](docs/09-optimization-methodology.md) |
| Optimizer kept out of the API runtime | Optuna, LightGBM and SHAP never enter a web request; the optimization UI reads the persisted study as data (a guard test enforces it) | [ADR-006](docs/adr/ADR-006-routine-optimizer.md), [ADR-008](docs/adr/ADR-008-optimization-surface-and-3d-replay.md) |
| Externalized RNG for the Numba kernel | Numba's in-kernel RNG cannot reproduce NumPy's Philox stream, so the draws are externalized and both paths consume them, giving a `1e-9` drop-in | [ADR-011](docs/adr/ADR-011-throughput-kernel.md) |
| Build vs buy, logged | Existing libraries are used wherever they fit; what is hand-built and why is recorded | [build-vs-buy ledger](docs/legacy-and-from-scratch.md) |

## Roadmap

Phases 0 through 9 are complete and merged: the physics core, player agents and the tactical engine,
Monte Carlo batches, the real-data xG model, the routine optimizer, the API and Scenario Workbench, the
optimization UI with 3D replay, wider scenario realism (`sim/0.5.0`), and evolutionary routine search
(NSGA-II and CMA-ES).

Phase 10, the Numba throughput kernel, is in progress: the RNG externalization and the njit agent
kernels have landed with `1e-9` equivalence tests; the fused per-sim kernel, the benchmark, and the
canonical re-baseline remain. The forward plan (calibration, multi-objective Pareto search, richer
fidelity) is in [docs/ROADMAP-future-enhancements.md](docs/ROADMAP-future-enhancements.md).

The complete design package (PRD, system architecture, data pipeline, simulation and ML architecture,
UI plan) lives in [docs/](docs/README.md).

## License and data

The original source code is released under the **MIT License** ([LICENSE](LICENSE)). The MIT grant
covers the code only. This project uses [StatsBomb open data](https://github.com/statsbomb/open-data)
under StatsBomb's non-commercial research terms, with attribution; that data is not redistributed here
(the marts are rebuilt locally by the ETL), and any use of the StatsBomb-derived data or of models
trained on it remains subject to StatsBomb's terms. No proprietary ratings data is used. This is a
research and portfolio project and is not affiliated with FIFA, StatsBomb, or any national federation.

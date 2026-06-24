# Restart Lab

**AI-assisted set-piece optimization for international football — built around the FIFA World Cup 2026.**

A physics-grounded simulator, agent-based player models, Monte Carlo experimentation, and
machine-learning-driven routine search, wrapped in an analyst-grade web platform. The question
it answers: *given our players and their defenders, what is the highest-value way to take this
corner, free kick, or throw-in?*

## Status

✅ **Phase 0 complete** — monorepo foundation: Python uv workspace (FastAPI backend +
simulation-core package), Next.js frontend, shared API types, CI, pre-commit, full
lint/type/test gates green.

✅ **Phase 1 complete** (`sim/0.1.0`) — ball physics core: RK4 flight with drag-crisis drag and
Magnus lift, Coulomb bounce with spin transfer, event-extracting trajectory simulator, and a
fused JIT batch engine (10k flights < 1 s single-core, equivalence-tested against a NumPy
reference and a SciPy oracle). See the
[assumptions registry](docs/simulation-assumptions.md) and
[ADR-001](docs/adr/ADR-001-physics-stack-build-vs-buy.md) /
[ADR-002](docs/adr/ADR-002-integration-strategy.md).

✅ **Phase 2 complete** (`sim/0.2.0`) — player agents and the tactical engine: validated player
attributes, Routine Spec `rs/1.0` compiled to array-form SimPrograms, defensive schemes with
marking and free-kick walls, and a deterministic set-piece engine that plays full corners to
terminal outcomes (goal/saved/cleared/keeper-claim/second-ball) with typed events and replay
tracks. Outcome rates intentionally uncalibrated until Phase 3.

✅ **Phase 3 complete** (`sim/0.3.0`) — Monte Carlo batches with Wilson confidence intervals,
outcome metrics, optimization interfaces (Optuna/CMA-ES-ready, no algorithms yet), and a working
**MVP vertical slice**: REST API + Scenario Workbench (`/workbench`) — pick a corner routine and
defensive scheme, simulate one delivery or a Monte Carlo batch, watch the animated pitch replay
and read goal/shot/clearance probabilities with CIs.

✅ **Phase 4** (`sim/0.4.0`) — StatsBomb ETL → marts, derived player profiles, and a calibrated
real-data xG model wired into the engine. ✅ **Phase 5** — the System B routine optimizer
(`restart-opt`): Optuna TPE vs an equal-budget random baseline, screen-then-confirm under common
random numbers, LightGBM+SHAP insights. ✅ **Phase 6** — the hardened API and the **Scenario
Workbench** on real squads from the marts: Build → Simulate (async runs, polled progress, xG
distributions + KPI/CI cards) → Replay (worst/median/best), with a Playwright E2E of the 3-minute
journey.

✅ **Phase 7** (parallel PR) — the **optimization UI** (`/optimize`: convergence ± CI, the
parallel-coordinates trial cloud, top-k vs baseline, plain-language SHAP insights), a workbench
**compare mode** (two scenarios under common random numbers; a winner only when the paired-difference
CI excludes zero), and **on-demand 3D replay** (React Three Fiber, dynamic-imported) over the same
replay JSON. ✅ **Phase 8** (`sim/0.5.0`) — **scenario realism**: the corner template now fields up to
**7 attackers** with off-ball roles (lurkers/recyclers, not seven bodies in the six-yard box), a
**basic free-kick genome**, and a structured `near_post_man` defence; the canonical study is
re-baselined. See [ADR-009](docs/adr/ADR-009-scenario-realism.md).

✅ **Phase 9** — **evolutionary routine search** (`restart-opt`): a genuine **NSGA-II** genetic
algorithm and **CMA-ES** evolution strategy plug into the same screen→confirm pipeline as TPE/random,
each trial carrying its **generation** lineage; the canonical study runs all three at equal budget and
records which sampler produced the winner. Honest result at the scoped budget: evolution beats random,
TPE still wins — a GA needs bigger populations/more generations, which Phase 10 unlocks. See
[ADR-010](docs/adr/ADR-010-evolutionary-search.md). The UI is also now production-grade: a persistent
app shell, real type system, and motion across the Workbench and Optimization surfaces.

```bash
# Run the Scenario Workbench locally:
uv run uvicorn restart_api.main:app --reload --app-dir apps/backend/src   # API :8000
npm run dev -w apps/frontend                                              # web :3000 -> /scenarios
```

🏗️ **In progress: Phase 10** — throughput: a fused **Numba scenario kernel** to lift the engine from
~3 sims/s toward 10⁴–10⁵ sims/s (the keystone that scales evolution). It externalizes the per-sim RNG
into a `SimDraws` draw plan so the njit kernel and the NumPy reference consume identical Philox draws —
a true `≤1e-9` drop-in (no `ENGINE_VERSION` bump). RNG externalization and the njit agent kernels have
landed with equivalence tests; the fused per-sim kernel, throughput benchmark, and canonical
re-baseline remain. See [ADR-011](docs/adr/ADR-011-throughput-kernel.md). The full forward roadmap —
calibration via simulation-based inference, multi-objective Pareto search, CVaR/robust objectives,
multi-touch fidelity — is in
[`docs/ROADMAP-future-enhancements.md`](docs/ROADMAP-future-enhancements.md).

The complete design package — PRD, system architecture, database schema, data pipeline,
simulation architecture, ML architecture, UI/UX plan, and 12-week roadmap — lives in
[`docs/`](docs/README.md).

## Key design decisions (and the rationale)

The "why did you build it this way?" answers, each with its canonical source:

| Decision | Rationale (short) | Where it's documented |
|---|---|---|
| **Pure-domain core** — `restart` imports no web/DB/ML/IO | The simulator stays a testable, deterministic library; every adapter (API, optimizer driver, ETL) depends inward, never the reverse | [ADR-005](docs/adr/ADR-005-data-platform-and-xg.md), [ADR-006](docs/adr/ADR-006-routine-optimizer.md) |
| **`ENGINE_VERSION` + determinism** — every persisted result carries the engine build id; same `Scenario` compiles byte-identical | Reproducibility is a product feature; physics/context-affecting changes bump the version (P8: `sim/0.4.0` → `sim/0.5.0`) so stale results are detectable, not silent | [restart/\_\_init\_\_.py](packages/simulation-core/src/restart/__init__.py), [ADR-009](docs/adr/ADR-009-scenario-realism.md) |
| **7-attacker template, fixed arity per study** | More attackers with off-ball roles makes the searched scenario realistic; arity stays *fixed within a study* so the search space is constant — keeping common-random-number pairing and SHAP attribution valid (variable-arity excluded, assumption O-2) | [ADR-009](docs/adr/ADR-009-scenario-realism.md) §1, [O-2](docs/handoff/ASSUMPTIONS_REGISTER.md) |
| **`fk_position` on the `Scenario`, not in the genome** | The kick origin is *study configuration*, not a thing to optimize; the genome searches delivery + runner behaviour, the wall is the defence's concern — so the free-kick and corner genomes share one builder and can't drift | [ADR-009](docs/adr/ADR-009-scenario-realism.md) §2, [genome.py](packages/simulation-core/src/restart/optimize/genome.py) |
| **Optimizer honesty** — mandatory equal-budget random baseline; no "winner" without non-overlapping/zero-excluding CIs | An optimizer that can't beat random search at equal budget is theatre; a "winner" without a significant CI is a deception trap | [doc 09](docs/09-optimization-methodology.md) §4–5 |
| **Throughput trade-off** — scoped study budgets, fused kernel deferred | The reference engine is ~3 sims/s; rather than block the product on a large kernel port, budgets are scoped + documented, and the kernel is a planned phase (now more pressing post-P8) | [ADR-006](docs/adr/ADR-006-routine-optimizer.md), [roadmap §1](docs/ROADMAP-future-enhancements.md) |
| **`restart_opt` out of the API runtime** — the optimization UI reads persisted `study.json` as data | Optuna/LightGBM/SHAP never enter a web request; searches are an offline/CLI concern, surfaced read-only (a guard test enforces the boundary) | ADR-006, ADR-008 (P7 branch) |
| **Hand-rolled SVG charts (not visx)** | visx peers cap at React 18; the app is React 19 — so charts are plain SVG, with R3F the sole exception for 3D | ADR-007 d7 (P7 branch) |

## The 60-second pitch

- **Simulate**: a vectorized physics engine (drag, Magnus, bounce) plus kinematically honest
  player agents play out a set piece 10,000 times in under a minute.
- **Measure**: goal/shot/first-contact probabilities with confidence intervals, scored by
  xG models trained on real World Cup and Euros data (StatsBomb Open Data).
- **Optimize**: Bayesian optimization searches the routine space — delivery, runs, screens,
  timing — and explains *why* the winners win.
- **Calibrate honestly**: simulated outcome rates are gated against real-world base rates
  before any predictive claim is made.

## Quickstart

Prerequisites: [uv](https://docs.astral.sh/uv/) ≥ 0.5, Node.js ≥ 24, Docker (optional, for
later phases). uv provisions Python 3.12 automatically.

```bash
git clone <repo-url> && cd Set-Piece-Sim
cp .env.example .env          # local config; never commit .env

uv sync --all-packages        # Python workspace (backend + simulation-core)
npm install                   # TypeScript workspace (frontend + shared-types)
uv run pre-commit install     # git hooks

# Run everything CI runs:
./scripts/verify.sh           # or: powershell -File scripts/verify.ps1

# Dev servers:
uv run uvicorn restart_api.main:app --reload --app-dir apps/backend/src   # API on :8000
npm run dev -w apps/frontend                                              # web on :3000
```

Full instructions: [docs/setup-guide.md](docs/setup-guide.md) ·
[docs/development-guide.md](docs/development-guide.md) · [CONTRIBUTING.md](CONTRIBUTING.md)

## Repository layout

```
apps/
  backend/      FastAPI application (restart_api) — web adapter, no domain logic
  frontend/     Next.js 16 app (TypeScript, Tailwind v4)
packages/
  simulation-core/  Pure-domain Python package (restart) — physics/agents/tactics/MC
  shared-types/     TypeScript mirrors of the API contract
data/           raw → staging → marts data lake (git-ignored, rebuildable)
docs/           design package + living guides
infra/          docker-compose (Postgres + Redis for later phases)
scripts/        verify.{sh,ps1} — the full CI suite, locally
tests/          cross-package integration tests
```

## Deploying

Two deployables, one recommended stack — **Fly.io** (backend), **Vercel** (frontend), **Neon**
(Postgres, only when scaling past the server-free default). Nothing is bespoke to these hosts; the
backend is a standard container and runs anywhere (Render, Railway, Cloud Run).

**Backend → Fly.io.** A [`fly.toml`](fly.toml) and a lean [`apps/backend/Dockerfile`](apps/backend/Dockerfile)
(backend + simulation core only — no optimizer/ML stack) are provided:

```bash
fly launch --no-deploy                                    # create the app (edit the name in fly.toml)
fly volumes create restart_data --size 1 --region lhr     # persists the marts + SQLite store
fly secrets set RESTART_CORS_ORIGINS='["https://YOUR-APP.vercel.app"]'
fly deploy
```

It boots **server-free** (SQLite + in-process queue) — no database required for the demo. To scale
out, set `RESTART_DATABASE_URL` (a Neon `postgresql+psycopg://…` URL) and `RESTART_REDIS_URL` (Upstash)
as secrets; the Postgres + Arq/Redis adapters are drop-ins. Liveness/readiness: `/healthz`, `/readyz`.

**Frontend → Vercel.** Zero-config; set the project root directory to `apps/frontend` and
`NEXT_PUBLIC_API_BASE_URL` to the Fly backend URL (plus `NEXT_PUBLIC_API_KEY` if the backend sets
`RESTART_API_KEY` for writes).

**Data.** `/optimize` works out of the box from the committed `optimization_studies/` (baked into the
image). The `/scenarios` squads + xG need the marts: run the StatsBomb ETL
([docs/etl-runbook.md](docs/etl-runbook.md)) to build `data/marts`, then upload them to the Fly volume
(the marts are derived locally and not redistributed — see License & data below).

For a plain container run anywhere:

```bash
docker build -f apps/backend/Dockerfile -t restart-api .
docker run -p 8000:8000 -e RESTART_CORS_ORIGINS='["https://your-frontend.example"]' \
  -v "$PWD/data:/app/data" restart-api
```

## License & data

The original source code is released under the **MIT License** ([LICENSE](LICENSE)). The MIT grant
covers the code only — it does not relicense third-party data. This project uses
[StatsBomb Open Data](https://github.com/statsbomb/open-data) under StatsBomb's **non-commercial**
research terms, with attribution; that data is **not redistributed** here (the derived marts are
rebuilt locally by the ETL), and any use of the StatsBomb-derived data or models trained on it
remains subject to StatsBomb's terms. No proprietary ratings data is used; every player attribute is
provenance-tagged. This is a research/portfolio project and is not affiliated with FIFA, StatsBomb,
or any national federation.

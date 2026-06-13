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

```bash
# Run the MVP locally:
uv run uvicorn restart_api.main:app --app-dir apps/backend/src   # API :8000
npm run dev -w apps/frontend                                     # web :3000 -> /workbench
```

🏗️ **Next: Phase 4** — ETL + real player profiles + xG v1; and the fused Numba scenario kernel
for 100k-sim batches.

The complete design package — PRD, system architecture, database schema, data pipeline,
simulation architecture, ML architecture, UI/UX plan, and 12-week roadmap — lives in
[`docs/`](docs/README.md).

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

## License & data

Code license TBD at first release. Uses [StatsBomb Open Data](https://github.com/statsbomb/open-data)
under its non-commercial research terms, with attribution. No proprietary ratings data is used;
every player attribute is provenance-tagged. This is a research/portfolio project and is not
affiliated with FIFA or any national federation.

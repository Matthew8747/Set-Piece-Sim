# Changelog

All notable changes to Restart Lab. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [SemVer](https://semver.org/) per package (the simulation engine additionally
carries its own `ENGINE_VERSION`, surfaced at `/healthz`).

## [Unreleased]

### Added — Phase 6: API & Scenario Workbench (2026-06-19) · `ENGINE_VERSION sim/0.4.0` (unchanged)

- **API hardening:** RFC 9457 problem-details for the whole surface; tightened input + pitch-coordinate
  bounds; per-IP rate limiting (slowapi; in-memory default, Redis when configured); `X-API-Key` write
  gate with bounded demo-mode; OpenAPI error schema + security metadata
  ([ADR-007](docs/adr/ADR-007-api-workbench-and-persistence.md)).
- **Real squads from the marts:** `MartSquadLoader` builds a pure `restart.Team` from
  `mart_players` / `mart_player_attributes` via a fixed deterministic XI rule (assumption **R9**);
  demo squads retired from the API runtime. `GET /api/v1/teams`, `GET /api/v1/players?team=<slug>`.
- **Persistence ports + async jobs:** `TeamRepository` / `ScenarioRepository` / `SimRunRepository`
  and a `JobQueue`, with server-free defaults (SQLite + in-process asyncio worker). `POST /scenarios`;
  `POST /sim-runs` (`202`, or `200` on idempotency hit — key = canonical scenario hash + `n_sims` +
  `seed` + `engine_version`); `GET /sim-runs/{id}` (status/progress/result with `xg_samples`);
  `GET /sim-runs/{id}/events?sample=worst|median|best` (single-sim replay). Determinism preserved
  end to end: same key ⇒ identical surfaced result.
- **shared-types from OpenAPI:** `@restart/shared-types` is generated from the committed
  `openapi.json`; `verify.ps1` fails on drift (hand-mirroring retired).
- **`@restart/pitch-kit` (new workspace):** the canonical 105×68 SVG pitch, a `ReplayPlayer`
  (scrubber, event markers, keyboard, `prefers-reduced-motion`), and hand-rolled SVG chart
  primitives (`Histogram`, `Ecdf`, `KpiCard` with CI whisker + "how?"), plus the full doc-07
  token scale. Charts are plain SVG, not visx (React-19 peer block — ADR-007 d7).
- **Scenario Workbench:** `/scenarios` library + `/scenarios/[id]` host with Build / Simulate /
  Replay modes (B/S/R keys), real-squad pickers, async-run polling, distribution charts +
  KPI/CI cards, and replay with a worst/median/best sample picker. Determinism banner on every
  result; empty states teach.
- **Drop-in production adapters (tested, CI-skipped without a server):** idempotent Postgres mart
  loader (`restart-etl load-postgres`); Postgres repositories + an Arq/Redis `JobQueue` selected by
  `RESTART_DATABASE_URL` / `RESTART_REDIS_URL`; `infra/docker-compose.yml`; `/readyz` now really
  probes the configured backends.
- **E2E:** Playwright runs the 3-minute journey at a reduced deterministic budget (`n_sims=24`)
  booting the backend + Next as web servers.
- Docs: [API reference](docs/api/README.md), [frontend README](apps/frontend/README.md), ADR-007,
  assumption R9. `ENGINE_VERSION` **unchanged** — Phase 6 touches no engine physics.

### Fixed
- `MartSquadLoader` shared a single DuckDB connection across threads; the in-process job worker and a
  concurrent polling request could race on it and corrupt query results (a spurious "unknown team").
  Each query now runs on its own DuckDB cursor.

### Added — Phase 5: Optimization Engine (System B) (2026-06-14) · `ENGINE_VERSION sim/0.4.0` (unchanged)

- **Pure optimize core (`restart.optimize`)** — the genome, objective, statistics, and guards stay
  IO/ML-free in the simulation core: `genome.py` (typed mixed search space —
  Continuous/Int/Categorical — plus the ~13-dim `CornerGenome` over a zone grid and its
  genotype→`Scenario` builder; `DeliveryGenome` keeps the v1 delivery sub-space); the
  `RoutineObjective` now returns **mean xG per sim** (doc 06 §2.3), deterministic per
  (params, root_seed) for common random numbers, and reports counterattack risk without optimizing
  it; `confirm.py` (mean-xG CI, the non-overlap decision rule, the CRN confirm stage);
  `boundary.py` (anti-exploit bound-pinning + face-validity ceiling).
- **New `optimizer` package (`restart_opt`, CLI `restart-opt`)** — System B's search engine,
  isolating all Optuna/LightGBM/SHAP/MLflow + IO from the pure core: seeded **Optuna TPE** with a
  mandatory **random-search baseline at equal budget**; the engine-backed **screen-then-confirm**
  pipeline (small-budget screen with median pruning under common random numbers → top-k confirmed
  at a large budget; a discovery must beat the library baseline with non-overlapping 95% CIs);
  a **LightGBM + SHAP surrogate** turning the trial cloud into plain-language insights; an
  **±10% attribute sensitivity analysis** (routine-precise vs report-classes, doc 04 §3);
  study persistence (`optimization_studies/<name>/study.json`) and MLflow logging (SQLite backend).
- **Canonical study:** *England corners vs Argentina zonal* via `restart-opt canonical` (demo
  squads; mart-derived squads are Phase 6). Methodology in
  [docs/09-optimization-methodology.md](docs/09-optimization-methodology.md); writeup in
  [docs/case-studies/england-vs-argentina.md](docs/case-studies/england-vs-argentina.md).
- **Throughput decision (ADR-006):** the reference engine is ~3 sims/s (measured), so the fused
  Numba scenario kernel (ADR-003 d8) is **deferred** and study budgets are **scoped + configurable**;
  the 500-screen/10k-confirm figures remain the documented reference methodology. `ENGINE_VERSION`
  is **unchanged** (`sim/0.4.0`) — the optimizer does not touch engine physics.

### Added — Phase 4: Data Platform, Player Profiles & xG v1 (2026-06-14) · `ENGINE_VERSION sim/0.4.0`

- **`etl` package (`restart_etl`, CLI `restart-etl`)** — pure-data pipeline, raw → staging →
  marts (design doc 04). `fetch statsbomb` pulls WC 2022 + Euro 2024 to a byte-exact, manifested,
  git-ignored raw cache; `stage` applies the single owned coordinate transform
  (StatsBomb 120×80 → canonical 105×68 m, center origin, attack L→R; property-tested) and writes
  typed Parquet; `marts` builds the five products below + loads a file-based DuckDB warehouse;
  `gates` runs the mechanical license + distribution checks; `all` rebuilds the world.
- **Marts (real data):** `mart_setpiece_shots` (975 corner/FK shots, 75 goals, freeze-frame
  traffic features + goal label, grouped by match), `mart_calibration_targets` (real base
  rates), `mart_players` + `mart_player_attributes` (1,259 players × 12 derived,
  **provenance-tagged** `{source, method, license}` attributes — aerial-duel-derived heading,
  set-piece-completion-derived delivery, position-group literature/curated priors for the rest;
  clamped to engine bounds), `mart_defensive_schemes` (curated zonal/man/hybrid + empirical
  corner reference).
- **Mechanical license gate:** every mart row's `source` ∈ approved allow-list; forbidden
  scraped-ratings sources (EA/sofifa) named and rejected. Enforced in CI via unit tests, not a
  policy doc.
- **`ml` package (`restart_ml`, CLI `restart-xg`)** — System A xG, trained on **real data only**
  (never simulator output, doc 06 §1). `xg-header` + `xg-foot` calibrated logistic models with a
  full method comparison (LR vs HistGBM vs RandomForest vs XGBoost vs LightGBM) under
  **grouped-by-match CV**; Platt calibration on out-of-fold predictions; MLflow (SQLite backend)
  logs every run; generated **model card** (`docs/model-cards/xg-v1.md`). Shipped logistic
  calibration slope **1.00** (header & foot) — meets the 0.9–1.1 acceptance target. The decision
  to ship the logistic (keeping the core dependency-free) over the marginally-better RF is
  recorded with evidence.
- **Engine integration (pure-domain preserved):** new `restart.engine.xg` (`ShotContext`,
  `XGScorer` protocol, pure-NumPy `LogisticXGScorer`, `XGModelBundle`). `SetPieceEngine` accepts
  an injected scorer; shots emit a `ShotContext`, are scored, and resolve by Bernoulli on the
  real-data xG (G-14/G-15). The shipped coefficient bundle is committed under `models/` and
  loaded by the backend directly as JSON — no ML framework in the API runtime.
- **API:** Monte Carlo report now carries `mean_xg`, `n_xg_scored`, and `xg_model`; `ShotEvent`
  (and `EventDTO`) carry per-shot `xg`. shared-types mirrors updated.
- Docs: data dictionary v1 (CI-checked), ETL runbook, model card, ADR-005, assumptions G-14/G-15.
- New tests across `etl`, `ml`, engine xG, and the API xG acceptance path (all green).

### Changed — Engine `sim/0.3.0` → `sim/0.4.0`
- `ShotEvent` gained an `xg` field and the engine gained an xG-scored shot path (injected
  `XGScorer`). The default (no-scorer) path is unchanged and deterministic, but the engine's
  behavior set changed → `ENGINE_VERSION` bump. The placeholder GK-save logit (G-9) is retained
  as the fallback when no model is wired.

### Added — Phase 3: Monte Carlo, Analytics & MVP (2026-06-13) · `ENGINE_VERSION sim/0.3.0`

- `restart.montecarlo`: seeded batch runner (`sim_seeds` — per-sim seeds stable across batch
  sizes, any sim replayable singly), outcome aggregation with **Wilson 95% CIs** (SciPy, M-2),
  serializable `SimulationReport` (goal / shot / header / first-contact / clearance /
  possession-recovery probabilities, PRD FR-4.2).
- `restart.optimize`: optimization *interfaces only* (no algorithms, per phase scope) —
  `SearchSpace`, `ContinuousParam`, `ObjectiveFunction` protocol, `RoutineObjective`
  (delivery-param mutation → compile → Monte Carlo → P(goal), deterministic per seed for CRN).
  Optuna/CMA-ES/GA plug in here in Phase 5.
- **MVP vertical slice (integration proof):** REST API `/api/v1/setpieces/{routines,schemes,
  simulate,montecarlo}` (n_sims hard-bounded for cost-bomb protection) + typed `shared-types`
  mirrors + Next.js **Scenario Workbench** (`/workbench`): routine/scheme selector, single-sim
  and Monte Carlo triggers, CI results panel, event timeline, animated SVG pitch replay with
  scrubber.
- ~30 new tests (410 Python + 3 frontend, all green).

### Changed
- Engine ball-flight horizon capped at 4 s (`EngineConfig.ball_sim_horizon_s`): set pieces
  resolve in 2–4 s, and integrating roll-to-rest tails cost ~10× per sim. Shifts some
  untouched-ball second-ball classifications → `ENGINE_VERSION` bump to `sim/0.3.0`.

### Performance
- `domain.vectors.cross` hand-expanded (np.cross routes through moveaxis, ~100× slower on
  small arrays; was ~25% of engine time) and `agents.separate` vectorized to process only
  overlapping pairs — both equivalence-preserving. Reference-engine MC ≈ 3 sims/s; the fused
  batch scenario kernel (ADR-003 d8) remains the 100k-sim answer (Phase-3 follow-up).

### Added — Phase 2: Agents & Tactical Engine (2026-06-12) · `ENGINE_VERSION sim/0.2.0`

- `restart.players`: validated attribute model with kernel-facing column contract
  (`Attr` IntEnum — compiled-program ABI), `Player`/`Team` entities, deterministic synthetic
  demo squads (no licensed ratings data).
- `restart.agents`: accel/turn-rate-limited kinematics, reaction-latency gating,
  accelerate-then-cruise interception solver, soft-disc separation (G-1..G-7).
- `restart.tactics`: Routine Spec `rs/1.0` (validating, rejecting), defensive schemes
  (zonal/man/hybrid + FK wall), `compile_scenario` → SoA `SimProgram` (ADR-004); library of
  5 corner routines + 3 schemes + direct free kick.
- `restart.engine`: `SetPieceEngine` — delivery execution (range-solved elevation, curl
  pre-aim, skill noise), pre-kick run development, kick-instant interception planning,
  Gumbel-max aerial contests, header/clearance/GK-claim contact resolution, logistic GK save
  model, second-ball classification; typed match events (`FirstContactEvent`, `ShotEvent`
  with embedded xG features, etc.) and `SetPieceOutcome`; deterministic replay payloads
  (agent tracks + trajectories) per seed.
- ADR-003 (agent architecture for Monte Carlo throughput), ADR-004 (Routine Spec contract),
  Phase-2 design review with throughput-risk assessment; `docs/handoff/` package (7 docs).
- G-1..G-13 registered in the assumptions registry. Free-kick feasibility validated (PRD A-3).
- ~120 new tests (251 total).

### Fixed
- Inswinger/outswinger spin-sign convention (verified against Magnus force direction).
- Corner kick position moved onto the corner arc (0.3 m inside both lines).

### Known limitations (Phase-3 targets)
- Outcome rates uncalibrated (keeper-claim share high; goal rate ~5% vs real 2–3%); all
  rate-shaping constants are named `EngineConfig` calibration knobs.

### Added — Phase 1: Ball Physics Core (2026-06-12) · `ENGINE_VERSION sim/0.1.0`

- **Build-vs-buy assessment** for the physics/simulation stack:
  [ADR-001](docs/adr/ADR-001-physics-stack-build-vs-buy.md) (NumPy + SciPy-as-oracle +
  Numba adopted-on-measurement + pydantic config; PyBullet/Pymunk/JAX rejected with rationale)
  and [ADR-002](docs/adr/ADR-002-integration-strategy.md) (fixed-step RK4, broadcast-polymorphic
  kernels, interpolated events).
- `restart.domain.vectors`: typed broadcast-polymorphic 3-vector utilities; pitch module gains
  goal-mouth and corner-position helpers.
- `restart.physics`: frozen pydantic config models with assumption-ID provenance (`BallConfig`,
  `DragConfig`, `MagnusConfig`, `EnvironmentConfig` incl. altitude presets, `BounceConfig`,
  `IntegratorConfig`); immutable `BallState` (9-dim packed state); extensible force
  architecture (`ForceModel` protocol, `Gravity`, `QuadraticDrag` with logistic drag crisis,
  `MagnusLift` with spin-parameter clamp, `ForceSystem` composition); RK4 integrator with
  in-state spin decay; Coulomb stick/slide bounce model with spin transfer; event-extracting
  `TrajectorySimulator` (launch/apex/bounce/goal/out-of-play/rest, interpolated timings);
  batch flight engine with fused Numba kernel (production) + NumPy reference (oracle).
- `restart.simulation`: typed event schemas (`SimEvent` hierarchy, `TerminationReason`) and
  layer protocols (`ForceModel`, `BallSimulator`).
- Validation framework: analytic closed-form oracles, SciPy DOP853 cross-check (< 1 cm /
  33 m delivery), RK4 convergence-order test, terminal-velocity check, Hypothesis
  energy-invariant property for bounce, Roberto Carlos 1997 plausibility recreation,
  kernel↔reference equivalence (≤ 1e-9).
- Benchmark framework: pytest-benchmark suite + throughput gate. Measured: 10k flights
  0.98 s single-core (10.2k flights/s) — 6.9× the NumPy path, meeting the roadmap budget.
- [Simulation assumptions registry](docs/simulation-assumptions.md): P-1…P-15 with citations,
  calibration-knob tags, and V1 validation evidence.
- 98 new tests (130 total).

### Added — Phase 0: Repository Foundation (2026-06-11)

- Monorepo: uv workspace (Python 3.12) + npm workspaces under one roof.
- `packages/simulation-core` (`restart`): pure-domain package with the canonical 105×68 m
  coordinate frame, pitch geometry constants, `ENGINE_VERSION`, and `py.typed`.
- `apps/backend` (`restart_api`): FastAPI skeleton — app factory with settings injection,
  `RESTART_`-prefixed pydantic-settings (SecretStr secrets, no credentialed defaults),
  `/healthz`, `/readyz`, `/api/v1/meta`, CORS, typed DTOs.
- `apps/frontend`: Next.js 16 (App Router, Turbopack) + TypeScript strict + Tailwind v4,
  dark "match-ops" design tokens seeded, Vitest + Testing Library harness.
- `packages/shared-types`: TypeScript mirrors of the API contract, consumed source-form via
  `transpilePackages`.
- Tooling: ruff, black, mypy (strict), pytest (importlib mode), eslint (flat config),
  prettier, pre-commit hooks.
- CI: GitHub Actions — python job (ruff/black/mypy/pytest) + frontend job
  (build/eslint/tsc/vitest/prettier).
- `scripts/verify.{sh,ps1}`: the full CI suite, runnable locally on any OS.
- `infra/docker-compose.yml`: Postgres 16 + Redis 7 (localhost-bound) for later phases.
- Data lake skeleton (`data/raw|staging|marts`, git-ignored) with layout README.
- Documentation: README quickstart, setup guide, development guide, contributing guide;
  design package (docs/01–08) updated to as-built layout.

### Security

- npm `overrides` forces postcss ≥ 8.5.10 (GHSA-qx2v-qp2m-jg93) under Next 16 stable;
  0 `npm audit` findings at commit time.
- Secrets policy enforced from the first commit: env-only config, `.env.example` template,
  `detect-private-key` pre-commit hook.

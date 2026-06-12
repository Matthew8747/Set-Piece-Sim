# Changelog

All notable changes to Restart Lab. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [SemVer](https://semver.org/) per package (the simulation engine additionally
carries its own `ENGINE_VERSION`, surfaced at `/healthz`).

## [Unreleased]

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

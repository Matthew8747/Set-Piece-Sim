# Phase Handoff

> Rewritten at the end of every completed phase.

## Last completed phase: Phase 6 — API & Scenario Workbench (`restart_api`, `@restart/pitch-kit`)

### What shipped

- **API hardening** — RFC 9457 problem-details across the surface; tightened request + pitch-coordinate
  bounds; per-IP rate limiting (slowapi); `X-API-Key` write gate with bounded demo mode; OpenAPI error
  schema + security metadata.
- **Real squads from the marts** — `MartSquadLoader` reads `mart_players` / `mart_player_attributes`
  and emits a pure `restart.Team` via a fixed deterministic XI rule (assumption **R9**). Demo squads
  retired from the runtime. `GET /teams`, `GET /players?team=<slug>`.
- **Persistence ports + async jobs** — `TeamRepository` / `ScenarioRepository` / `SimRunRepository`
  and a `JobQueue` Protocol, with server-free defaults (SQLite + in-process asyncio worker). Sim runs
  are idempotent by canonical scenario hash folded with `n_sims` + `seed` + `engine_version`;
  `POST /sim-runs` (202/200), `GET /sim-runs/{id}` (status/progress/result + `xg_samples`),
  `GET /sim-runs/{id}/events?sample=worst|median|best`.
- **shared-types from OpenAPI** — generated from the committed `openapi.json`; `verify.ps1` drift gate.
- **`@restart/pitch-kit`** — canonical SVG `Pitch`, `ReplayPlayer` (scrubber/keyboard/reduced-motion),
  hand-rolled SVG charts (`Histogram`/`Ecdf`/`KpiCard`), and the full doc-07 token scale.
- **Scenario Workbench** — `/scenarios` library + `/scenarios/[id]` Build/Simulate/Replay (B/S/R keys),
  real-squad pickers, polling progress, distributions + KPI/CI cards, determinism banner, replay
  sample picker.
- **Production drop-ins (tested, CI-skipped without a server)** — Postgres mart loader
  (`restart-etl load-postgres`), Postgres repositories + Arq/Redis queue selected by config,
  `infra/docker-compose.yml`, real `/readyz` probes.
- **E2E** — Playwright 3-minute journey at a reduced deterministic budget (`n_sims=24`).
- Docs: [ADR-007](../adr/ADR-007-api-workbench-and-persistence.md), [API reference](../api/README.md),
  [frontend README](../../apps/frontend/README.md), [CHANGELOG](../../CHANGELOG.md) Phase-6 entry.
  `ENGINE_VERSION` **unchanged** (`sim/0.4.0`).

### Validation evidence

All `scripts/verify.ps1` gates green (ruff, black, mypy --strict, pytest, next build, eslint, tsc,
vitest, prettier, OpenAPI/shared-types drift). pitch-kit: 13 vitest tests; frontend: 8 vitest;
Playwright journey passes locally (build → 24-sim run → distributions → replay). Postgres/Arq adapter
tests are marked `postgres`/`redis` and skip without `RESTART_TEST_DATABASE_URL` / `RESTART_TEST_REDIS_URL`.

### Debugging history worth knowing (saves future sessions time)

1. **DuckDB connections are not thread-safe.** `MartSquadLoader` shared one connection; the in-process
   job worker (`asyncio.to_thread`) and a concurrent polling request raced on it and corrupted results
   — a spurious "unknown team". Fix: issue each query on its own `con.cursor()`. Any future
   threaded/duckdb access must do the same.
2. **A failed sim run is cached by idempotency key.** During E2E a (pre-fix) failure was stored and
   every re-run with the same spec+seed returned it. Bust by changing the seed or clearing the store
   (`.e2e-data`); don't wipe the store mid-run (it drops tables under the live server).
3. **Tailwind v4 resolves a package `@import`.** `globals.css` imports `@restart/pitch-kit/tokens.css`
   (an `@theme` block) so utilities + raw vars come from one scale — validated via `next build`.
4. **Scenario spec is ids-only by design.** The Build planning handles are a local annotation; the
   engine simulates the *selected routine*. Persisting custom geometry would be a backend change.
5. **Playwright loads its config as CommonJS** — use `__dirname`, not `import.meta`.

### Open decisions carried forward (NOT touched by Phase 6)

- **Engine `[knob]` calibration (🔴)** — simulated shot-context distribution still unvalidated
  (goal ~5% sim vs 2–3% real); `mart_calibration_targets` holds the real base rates to fit.
- **Fused Numba scenario kernel (🔴)** — the path to 10⁵–10⁶-sim studies; still deferred.
- **First-contact-only fidelity (O-3)** — no multi-touch / lookahead / defender anticipation.
- **E2E in CI** — the journey runs locally; wiring it into CI is gated on provisioning the committed
  marts in CI (the same precondition the data-dependent pytest suite already has).

## Next phase: Phase 7 — Optimization UI & 3D replay (roadmap weeks 11–12)

Scope (doc 07 IA): an optimization surface over `restart_opt` studies (convergence with best-so-far
± CI band, parallel-coordinates of trials, top-k vs baseline, the SHAP "insights" panel); 3D replay
(R3F, dynamic-imported) consuming the same replay JSON the 2D player already uses; team-intelligence
(squad aerial/pace profiles, mismatch matrix) and an exportable print-CSS report. Compare mode in the
workbench (two scenarios, common-random-number difference CI; **no winner badge without significance**)
is the natural first add.

### Risks for Phase 7
1. R3F bundle weight — load only on demand; keep 2D as the default and the SVG-only fallback.
2. Optimization studies are heavy/long — surface persisted `study.json` artifacts, don't run searches
   from the browser.
3. The carried-forward 🔴 calibration still caps how literally any "winner" should be read — keep
   reporting routine *classes* until the shot-context distribution is validated.

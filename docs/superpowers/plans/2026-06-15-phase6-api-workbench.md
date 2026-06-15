# Phase 6 — API & Scenario Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Restart Lab usable by a non-author — harden the FastAPI surface, run Monte Carlo as async jobs with progress, persist scenarios behind swappable file/Postgres adapters, wire **real squads** from the marts (retire demo squads), and ship a Scenario Workbench (Build / Simulate / Replay) plus a Playwright E2E of the 3-minute journey.

**Architecture:** Ports-and-adapters everywhere infrastructure touches the web layer. `apps/backend` (`restart_api`) stays the only adapter; `packages/simulation-core` (`restart`) stays pure (no web/DB/ML/IO imports). Repositories and a `JobQueue` are Protocols with a **file-first default** (DuckDB/SQLite/Parquet — server-free CI) and tested **Postgres/Arq** drop-in adapters. `ENGINE_VERSION` does **not** change (`sim/0.4.0` — no engine behaviour touched). Determinism is preserved end to end: same `(scenario, seed, engine_version)` ⇒ identical surfaced result, enforced by the scenario hash used as the idempotency key.

**Tech Stack:** FastAPI · pydantic v2 · slowapi (rate limit) · Arq + Redis (optional prod job adapter) · psycopg (optional Postgres adapter) · DuckDB/SQLite (default stores) · Next.js 16 / React 19 · hand-rolled SVG chart primitives (see note) · openapi-typescript (DTO codegen) · Playwright (E2E). uv for Python, npm workspaces for TS.

> **Deviation (recorded in ADR-007):** doc 07 names *visx* for charts, but visx 3.x peers cap at React 18 and the app is React 19 (hard `ERESOLVE`); no React-19-compatible visx release exists. Rather than loosen peer resolution repo-wide, the histogram / ECDF / KPI-CI-whisker — all simple — are hand-rolled as plain SVG in pitch-kit. This honors doc 07's stated intent ("custom SVG, React owns the DOM, not a charting template") and drops a blocked dependency.

---

## Locked execution decisions (from Phase 6 kickoff)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Persistence posture | **Ports, file-first default.** Repository ports; default file adapters (DuckDB/SQLite/Parquet, server-free CI); Postgres adapters shipped + tested as drop-ins. docker-compose for the PG path. |
| 2 | Async jobs | **JobQueue port.** In-process asyncio worker is the CI/dev default; Arq+Redis adapter for prod. Progress + idempotency via polling GET. |
| 3 | Workbench Build depth | **Configure + constrained edit.** Real-squad select + routine/scheme pick + snap-to-grid handles for delivery target / key runner zone. Not a free-form choreographer. |
| 4 | shared-types sync | **OpenAPI codegen now.** `openapi-typescript` generates `@restart/shared-types`; CI fails on drift; hand-mirroring retired. |
| 5 | Progress transport | **Polling** (roadmap-settled; SSE deferred, reversible). |

## Hard constraints (verified each milestone)

- **Pure-domain:** `restart` imports no web/DB/ML/IO. All parquet/DB reads, Optuna, Arq live in adapters. `restart_opt` stays out of the API runtime (load `study.json` as data only).
- **Determinism:** scenario hash = canonical-JSON SHA-256 of the full spec; `(hash, seed, engine_version)` is the idempotency key; same key ⇒ same surfaced result.
- **No `ENGINE_VERSION` bump** (P6 is API/UI).
- **Gates green before every commit:** `scripts/verify.ps1` (ruff, black, mypy --strict, pytest, next build, eslint, tsc, vitest, prettier). New Python deps → the right `pyproject.toml` + `uv.lock`; mypy overrides for untyped libs (P4/P5 pattern). New TS deps → the right `package.json`.
- **No scraped ratings.** Real squads come only from `mart_players` / `mart_player_attributes` (provenance-tagged, StatsBomb-derived).
- **Carried-forward debt is NOT absorbed:** fused Numba scenario kernel (🔴), engine `[knob]` calibration (🔴), and first-contact-only fidelity (O-3) remain FUTURE ENGINE work — out of Phase 6.

## Throughput reality (drives async design)

Reference engine ≈ **3 sims/s** with xG wired. So 1k sims ≈ 5.5 min — synchronous requests would block and the E2E cannot run 1000 real sims in CI. Therefore: Monte Carlo runs as a **job**; the E2E journey runs a **reduced, deterministic budget** (`n_sims=24`, ≈ 8 s) while exercising the identical build→run→distributions→replay path. This is documented, not hidden; the workbench still offers the full bounded range for real use.

---

## File structure

### Backend (`apps/backend/src/restart_api/`)
```
errors.py                     # NEW: RFC 9457 problem-details handlers + domain-exception mapping
security.py                   # NEW: API-key dependency (require_write_access); demo-mode bounds
ratelimit.py                  # NEW: slowapi limiter factory (memory default, redis when configured)
hashing.py                    # NEW: canonical-JSON SHA-256 scenario_hash
squads/loader.py              # NEW: mart parquet -> pure restart.Team (the squad-from-marts wiring)
repositories/ports.py         # NEW: Protocols (TeamRepository, ScenarioRepository, SimRunRepository)
repositories/file.py          # NEW: SQLite/DuckDB + parquet adapters (default)
repositories/postgres.py      # NEW: Postgres adapters (drop-in; tested, skipped without PG)
jobs/queue.py                 # NEW: JobQueue Protocol + InProcessJobQueue (default)
jobs/arq_queue.py             # NEW: Arq adapter (prod; imported lazily)
jobs/runner.py                # NEW: pure-ish batch runner wrapper (chunked progress, xg samples)
routers/v1/teams.py           # NEW: GET /teams, GET /players?team=
routers/v1/scenarios.py       # NEW: POST/GET scenarios (validate + persist)
routers/v1/sim_runs.py        # NEW: POST /sim-runs, GET /sim-runs/{id}, GET /sim-runs/{id}/events
routers/v1/setpieces.py       # MODIFY: catalog stays; sim now via real squads + job path
schemas.py                    # MODIFY: add Team/Player/Scenario/SimRun/Problem DTOs
settings.py                   # MODIFY: add rate-limit + job + store config knobs
main.py                       # MODIFY: register error handlers, limiter, routers, lifespan(worker)
routers/health.py             # MODIFY: real readiness probes for configured store/queue
```

### ETL (`packages/etl/src/restart_etl/`)
```
marts/load_postgres.py        # NEW: idempotent DELETE-WHERE-source + insert PG loader (drop-in)
cli.py                        # MODIFY: `restart-etl load-postgres` subcommand
```

### Frontend
```
packages/pitch-kit/           # NEW workspace: SVG Pitch, ReplayPlayer, SVG chart primitives, tokens.css
apps/frontend/src/app/scenarios/page.tsx            # NEW: scenario library
apps/frontend/src/app/scenarios/[id]/page.tsx       # NEW: Scenario Workbench host
apps/frontend/src/components/workbench/*            # NEW: Build/Simulate/Replay panels
apps/frontend/src/lib/api.ts                        # MODIFY: teams/scenarios/sim-runs + polling
apps/frontend/src/app/globals.css                   # MODIFY: full token scale (doc 07)
packages/shared-types/src/{generated.ts,index.ts}   # MODIFY: codegen output + curated re-exports
```

### Tests / docs
```
apps/backend/tests/test_{errors,security,ratelimit,squads,scenarios,sim_runs,jobs,idempotency}.py
packages/etl/tests/test_load_postgres.py
packages/pitch-kit/src/*.test.tsx
apps/frontend/tests/e2e/journey.spec.ts             # Playwright
docs/adr/ADR-007-api-workbench-and-persistence.md
docs/api/README.md                                  # OpenAPI + curl
apps/frontend/README.md                             # frontend architecture
```

---

## Milestone map (each is an independently-shippable, verify-green slice)

- **M0** Branch + deps + ADR-007 (design recorded before code — bootstrap rule).
- **M1** API hardening: problem-details, bounds, rate limit, API keys, OpenAPI. *(no new infra)*
- **M2** Persistence ports + real squads from marts (retire demo squads in the sim path).
- **M3** Async jobs: JobQueue port, sim-runs endpoints, idempotency, progress, per-sim xG samples.
- **M4** shared-types OpenAPI codegen + CI drift gate.
- **M5** pitch-kit package (SVG pitch, replay player, visx charts, tokens).
- **M6** Scenario Workbench (library + Build/Simulate/Replay) on real endpoints.
- **M7** Playwright E2E + Postgres/Arq adapters + docs + handoff + PR.

> Execute in order; `scripts/verify.ps1` must be green before each milestone's final commit. Stop for review at the end of M1, M3, M6, and M7.

---

## M0 — Branch, dependencies, ADR

### Task 0.1: Create the phase branch

- [ ] **Step 1:** From `feat/phase5-optimizer` (current), branch.
```bash
git checkout -b feat/phase6-api-workbench
```
- [ ] **Step 2:** Confirm clean tree: `git status` → "nothing to commit, working tree clean".

### Task 0.2: Add backend dependencies

**Files:** Modify `apps/backend/pyproject.toml`; update `uv.lock`.

- [ ] **Step 1:** Add to `[project].dependencies`: `slowapi>=0.1.9`. Add optional groups so the default install stays light:
```toml
[project.optional-dependencies]
postgres = ["psycopg[binary]>=3.2"]
arq = ["arq>=0.26", "redis>=5.2"]
```
- [ ] **Step 2:** `uv sync --all-packages` → succeeds; `uv.lock` updated.
- [ ] **Step 3:** If mypy flags untyped `slowapi`, add to root `pyproject.toml` `[[tool.mypy.overrides]]` `module = "slowapi.*"`, `ignore_missing_imports = true` (P4/P5 pattern). Same for `arq.*`, `psycopg.*` when their adapters land.
- [ ] **Step 4:** Commit: `chore(backend): add slowapi + optional postgres/arq deps`.

### Task 0.3: Add frontend dependencies

**Files:** Modify `apps/frontend/package.json`, `packages/shared-types/package.json`.

> The pitch-kit workspace + its frontend dep land in **M5** (where the package is created), so `npm install` stays green at every milestone. Charts are hand-rolled SVG (see Deviation), so no visx.

- [ ] **Step 1:** `apps/frontend`: devDep `"@playwright/test"`.
- [ ] **Step 2:** `packages/shared-types`: devDep `"openapi-typescript": "^7"`; script `"gen": "openapi-typescript ../../apps/backend/openapi.json -o src/generated.ts"`.
- [ ] **Step 3:** `npm install` at root → succeeds.
- [ ] **Step 4:** Commit: `chore(frontend): add playwright + openapi-typescript`.

### Task 0.4: Record ADR-007 (design before code)

**Files:** Create `docs/adr/ADR-007-api-workbench-and-persistence.md`; update `docs/adr/README.md` index and `docs/handoff/ADR_SUMMARY.md`.

- [ ] **Step 1:** Write ADR-007 capturing: ports-and-adapters for persistence + jobs; file-first default vs Postgres/Arq drop-ins; RFC 9457 problem-details; scenario-hash idempotency; real squads from marts; OpenAPI codegen; reduced-budget E2E rationale; explicit non-goals (no kernel, no calibration, no multi-touch — carried forward). Status: Accepted (P6). `ENGINE_VERSION` unchanged.
- [ ] **Step 2:** Add the ADR-007 row to both index tables.
- [ ] **Step 3:** Commit: `docs(adr): ADR-007 API & Scenario Workbench architecture`.

---

## M1 — API hardening (no new infrastructure)

### Task 1.1: RFC 9457 problem-details errors

**Files:** Create `apps/backend/src/restart_api/errors.py`; Modify `main.py`; Test `apps/backend/tests/test_errors.py`.

- [ ] **Step 1 (test first):** assert validation + not-found render `application/problem+json`.
```python
# apps/backend/tests/test_errors.py
from fastapi.testclient import TestClient
from restart_api.main import create_app
from restart_api.settings import Settings

client = TestClient(create_app(Settings(app_env="test")))

def test_validation_error_is_problem_json():
    r = client.post("/api/v1/setpieces/montecarlo",
                    json={"routine_id": "x", "scheme_id": "y", "n_sims": 999999})
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["status"] == 422 and "type" in body and "title" in body

def test_unknown_routine_is_problem_json():
    r = client.post("/api/v1/setpieces/montecarlo",
                    json={"routine_id": "nope", "scheme_id": "nope", "n_sims": 1})
    assert r.status_code == 404
    assert r.json()["status"] == 404
```
- [ ] **Step 2:** Run `uv run pytest apps/backend/tests/test_errors.py -v` → FAIL (content-type is `application/json`).
- [ ] **Step 3 (implement):** `errors.py` — handlers mapping `RequestValidationError`, `StarletteHTTPException`, and domain exceptions (`InvalidRoutine`, `InfeasibleAssignment`, `CalibrationGateFailure` if importable from `restart`) to a `ProblemDetail` model `{type,title,status,detail,instance,errors?}`, media type `application/problem+json`. Provide `install_error_handlers(app)`.
- [ ] **Step 4:** `main.py`: call `install_error_handlers(app)` in `create_app`.
- [ ] **Step 5:** Run the test → PASS. Add `ProblemDetail` to `schemas.py` so it appears in OpenAPI.
- [ ] **Step 6:** Commit: `feat(api): RFC 9457 problem-details error responses`.

### Task 1.2: Tightened input bounds + canonical pitch-coordinate validation

**Files:** Modify `schemas.py`; Test `apps/backend/tests/test_setpieces.py` (extend).

- [ ] **Step 1 (test):** out-of-range `n_sims`, negative seed, and (new) any pitch-coordinate field outside `[0,105]×[0,68]` are rejected 422. (Coordinate bounds become relevant in scenarios — Task 3.x; add a shared `PitchPoint` validator now.)
- [ ] **Step 2:** Add `PitchPoint(BaseModel)` with `x: float = Field(ge=0, le=105)`, `y: float = Field(ge=0, le=68)`; reuse in scenario DTOs.
- [ ] **Step 3:** Run tests → PASS. Commit: `feat(api): pitch-coordinate bounds + stricter request validation`.

### Task 1.3: Rate limiting (memory default, Redis when configured)

**Files:** Create `ratelimit.py`; Modify `settings.py`, `main.py`, routers; Test `test_ratelimit.py`.

- [ ] **Step 1 (test):** with a tiny test limit, the N+1th POST to a compute endpoint returns 429 + problem-json.
- [ ] **Step 2:** `settings.py`: add `rate_limit_read: str = "120/minute"`, `rate_limit_write: str = "20/minute"`, `max_concurrent_jobs: int = 2`.
- [ ] **Step 3:** `ratelimit.py`: build a `slowapi.Limiter` keyed by client IP; `storage_uri` = `redis_url` if set else in-memory. Export `limiter` + a `RateLimitExceeded` → problem-json handler.
- [ ] **Step 4:** `main.py`: attach `app.state.limiter`, register handler. Decorate compute POSTs with `@limiter.limit(...)`.
- [ ] **Step 5:** Run test → PASS. Commit: `feat(api): per-IP rate limiting on read/compute endpoints`.

### Task 1.4: API-key write access + demo-mode bounds

**Files:** Create `security.py`; Modify routers, `main.py`; Test `test_security.py`.

- [ ] **Step 1 (test):** when `Settings(api_key=...)` is set, a write endpoint without `X-API-Key` → 401 problem-json; with the correct key → allowed. When `api_key` is unset (demo), bounded writes allowed; oversized `n_sims` still 422.
- [ ] **Step 2:** `security.py`: `require_write_access(settings, x_api_key: str | None)` dependency — constant-time compare against `settings.api_key.get_secret_value()`; if unset → demo mode (allow, bounds enforced by schema). Raise 401 via problem-json otherwise.
- [ ] **Step 3:** Apply the dependency to write/compute routes (`montecarlo`, `simulate`, later `scenarios`, `sim-runs`).
- [ ] **Step 4:** OpenAPI: declare an `ApiKeyHeader` security scheme so `/docs` shows it.
- [ ] **Step 5:** Run test → PASS. Commit: `feat(api): API-key gate on writes with demo-mode bounded access`.

### Task 1.5: OpenAPI polish + route-coverage test

**Files:** Modify `main.py`; Test `apps/backend/tests/test_setpieces.py` / a `test_openapi.py`.

- [ ] **Step 1 (test):** `app.openapi()` includes every mounted route, declares `ProblemDetail` as the error schema, and lists the security scheme.
- [ ] **Step 2:** Set FastAPI `responses` defaults (4xx/5xx → `ProblemDetail`), `servers`, tags.
- [ ] **Step 3:** Run test → PASS. **Run `scripts/verify.ps1` → all green.** Commit: `feat(api): OpenAPI error schema, servers, security metadata`.

> **REVIEW CHECKPOINT 1** — API hardening complete, no new infra, all gates green.

---

## M2 — Persistence ports + real squads from marts

### Task 2.1: Squad loader (mart parquet → pure `restart.Team`)

**Files:** Create `apps/backend/src/restart_api/squads/loader.py`; Test `apps/backend/tests/test_squads.py`.

This is the squad-from-marts wiring. Reading lives in the adapter; output is a pure `restart.players.Team`. The marts ship committed in `data/marts/`.

- [ ] **Step 1 (test):** loading a known country (e.g. "England") returns a valid `Team` (≥11 players, has a GK), with attributes inside engine bounds, and is deterministic (same call ⇒ identical player ids/order).
```python
# apps/backend/tests/test_squads.py
from pathlib import Path
from restart.players.team import Team
from restart.players.player import PositionGroup
from restart_api.squads.loader import MartSquadLoader

MARTS = Path(__file__).resolve().parents[3] / "data" / "marts"

def test_loads_real_team_as_pure_domain_team():
    loader = MartSquadLoader(MARTS)
    team = loader.team("England")
    assert isinstance(team, Team)
    assert len(team.players) >= 11
    assert any(p.position_group is PositionGroup.GK for p in team.players)

def test_team_selection_is_deterministic():
    loader = MartSquadLoader(MARTS)
    a = [p.player_id for p in loader.team("England").players]
    b = [p.player_id for p in loader.team("England").players]
    assert a == b
```
- [ ] **Step 2:** Run → FAIL (`MartSquadLoader` missing).
- [ ] **Step 3 (implement):** `MartSquadLoader(marts_dir)`:
  - Read `mart_players.parquet` + `mart_player_attributes.parquet` via duckdb (already a dep) or pyarrow.
  - Filter by `team` (StatsBomb team name) — or `country` for national teams; pick the column that matches the marts (verify with a quick `duckdb` describe at implement time).
  - **Selection rule (deterministic XI):** group attribute rows per `player_id` into a `PlayerAttributes`; map `position_group` string → `PositionGroup` (assert all four map; raise on unknown). Choose 1 GK (most appearances; tie → lowest player_id) + 10 outfield by a fixed priority (DF/MF/FW quota 4/4/2; within group rank by `heading + delivery` desc, tie → player_id). Stable sort everywhere.
  - Build `Player(player_id=str(pid), display_name=name, position_group=..., attributes=...)`; assemble `Team(team_id=<slug>, name=<team>, players=tuple(...))`.
  - Clamp/validate via the existing `PlayerAttributes` bounds (loader passes through; mart values already clamped).
- [ ] **Step 4:** Run tests → PASS.
- [ ] **Step 5:** Commit: `feat(api): load real squads from mart_players/attributes (pure Team output)`.

### Task 2.2: Repository ports + file adapters

**Files:** Create `repositories/ports.py`, `repositories/file.py`; Test `test_scenarios.py` (store round-trip).

- [ ] **Step 1 (test):** a `ScenarioRecord` saved via the file `ScenarioRepository` round-trips by id; `TeamRepository.list_teams()` returns the mart teams; `get(team_id)` returns a `Team`.
- [ ] **Step 2 (implement ports):** Protocols:
```python
# repositories/ports.py
class TeamRepository(Protocol):
    def list_teams(self) -> list[TeamSummary]: ...
    def get(self, team_id: str) -> Team: ...           # pure restart.Team
class ScenarioRepository(Protocol):
    def create(self, rec: ScenarioRecord) -> ScenarioRecord: ...
    def get(self, scenario_id: str) -> ScenarioRecord | None: ...
    def list(self, limit: int) -> list[ScenarioRecord]: ...
class SimRunRepository(Protocol):
    def create(self, run: SimRunRecord) -> SimRunRecord: ...
    def get(self, run_id: str) -> SimRunRecord | None: ...
    def by_idempotency_key(self, key: str) -> SimRunRecord | None: ...
    def update(self, run: SimRunRecord) -> None: ...
```
- [ ] **Step 3:** `repositories/file.py`: `MartTeamRepository` (wraps `MartSquadLoader`); `SqliteScenarioRepository` + `SqliteSimRunRepository` over a SQLite file at `settings.data_dir/restart_app.sqlite` (JSON columns for specs/results). Create tables on first use (idempotent `CREATE TABLE IF NOT EXISTS`).
- [ ] **Step 4:** Run tests → PASS. Commit: `feat(api): repository ports + file (SQLite/mart) adapters`.

### Task 2.3: Retire demo squads in the sim path

**Files:** Modify `routers/v1/setpieces.py`, add `routers/v1/teams.py`, `schemas.py`; Test `test_teams.py`, extend `test_setpieces.py`.

- [ ] **Step 1 (test):** `GET /api/v1/teams` lists real teams; `GET /api/v1/players?team=England` lists real players with provenance; `simulate`/`montecarlo` accept `attacking_team_id`/`defending_team_id` and run against real squads; determinism (same seed ⇒ same outcome) holds.
- [ ] **Step 2:** Add `TeamSummary`, `PlayerDTO` (with `source`/provenance) to `schemas.py`; extend `SimulateRequest`/`MonteCarloRequest` with `attacking_team_id`, `defending_team_id` (defaults = the canonical England/Argentina mart slugs so existing callers keep working).
- [ ] **Step 3:** `teams.py`: `GET /teams`, `GET /players`. Wire `setpieces.py` to build the program from `TeamRepository.get(...)` instead of `demo_team(...)`. Keep the kicker/role-assignment logic; it already keys off `attributes.delivery` and `PositionGroup`.
- [ ] **Step 4:** Run tests → PASS. **verify.ps1 green.** Commit: `feat(api): real squads in sim endpoints; /teams + /players (demo squads retired)`.

> Demo squads remain only for unit tests of the core (licensing-safe synthetic fixtures) — they are no longer in the API runtime path.

---

## M3 — Async jobs, idempotency, progress

### Task 3.1: Scenario hash (idempotency key)

**Files:** Create `hashing.py`; Test `test_idempotency.py`.

- [ ] **Step 1 (test):** `scenario_hash` is canonical (key order independent), stable, and changes when any field changes; the idempotency key folds in `seed` + `engine_version`.
```python
def test_scenario_hash_is_canonical_and_stable():
    a = scenario_hash({"routine_id": "r", "scheme_id": "s", "att": "England"})
    b = scenario_hash({"att": "England", "scheme_id": "s", "routine_id": "r"})
    assert a == b and len(a) == 64
```
- [ ] **Step 2:** Implement `scenario_hash(spec) -> str` = SHA-256 of `json.dumps(spec, sort_keys=True, separators=(",",":"))`; `idempotency_key(spec, seed, engine_version)` folds all three.
- [ ] **Step 3:** Run → PASS. Commit: `feat(api): canonical scenario hash + idempotency key`.

### Task 3.2: Batch runner with chunked progress + per-sim xG samples

**Files:** Create `jobs/runner.py`; Test `test_jobs.py`.

- [ ] **Step 1 (test):** `run_batch` over a program yields the same aggregate report as `build_report(MonteCarloRunner...)` for the same seed (determinism), reports progress monotonically 0→1, and returns a bounded `xg_samples` list (≤ `MAX_XG_SAMPLES`) for the distribution chart.
- [ ] **Step 2:** `jobs/runner.py`: wrap `MonteCarloRunner` to execute in chunks (e.g. 50 sims), invoke a `progress(done, total)` callback after each chunk, collect per-sim xG into a reservoir-sampled list (deterministic: seeded by `root_seed`). Return `(report_dict, xg_samples)`. Pure compute; no IO.
- [ ] **Step 3:** Run → PASS. Commit: `feat(api): chunked batch runner with progress + xG sample collection`.

### Task 3.3: JobQueue port + in-process adapter

**Files:** Create `jobs/queue.py`; Modify `main.py` (lifespan); Test `test_jobs.py` (lifecycle).

- [ ] **Step 1 (test):** submitting a job transitions `queued → running → complete`, persists the result via `SimRunRepository`, and respects `max_concurrent_jobs`. A second submit with the same idempotency key returns the existing run (no re-run).
- [ ] **Step 2:** `jobs/queue.py`: `JobQueue(Protocol)` with `submit(run_id)`; `InProcessJobQueue` using `asyncio.create_task` + a `Semaphore(max_concurrent_jobs)`; worker loads the `SimRunRecord`, builds the program, calls `run_batch` with a `progress` callback that writes `progress` back through the repo. Errors → `status=failed` + structured `error_json`.
- [ ] **Step 3:** `main.py`: build the queue in a `lifespan` context; expose via `app.state` / a dependency.
- [ ] **Step 4:** Run → PASS. Commit: `feat(api): JobQueue port + in-process async worker`.

### Task 3.4: sim-runs endpoints

**Files:** Create `routers/v1/sim_runs.py`, `routers/v1/scenarios.py`; Modify `schemas.py`, `routers/v1/__init__.py`; Test `test_sim_runs.py`, `test_scenarios.py`.

- [ ] **Step 1 (test):** `POST /scenarios` validates + persists, returns id; `POST /sim-runs {scenario_id, n_sims, root_seed}` returns `202` + run id (or `200` + existing on idempotency hit); `GET /sim-runs/{id}` polls status/progress; on complete it carries the aggregate report + `xg_samples`; `GET /sim-runs/{id}/events?sample=replay` returns a sampled replay trajectory.
- [ ] **Step 2:** Add `ScenarioCreate`, `ScenarioRecord`, `SimRunCreate`, `SimRunStatus`, `SimRunResult` DTOs (reusing `MonteCarloResponse` fields + `xg_samples`). Implement routers; gate writes with `require_write_access` + rate limit.
- [ ] **Step 3:** Run → PASS. **verify.ps1 green.** Commit: `feat(api): async sim-runs + scenarios endpoints with idempotency + progress`.

> **REVIEW CHECKPOINT 2** — full async API contract complete; demo→real squads; deterministic surfaced results.

---

## M4 — shared-types OpenAPI codegen

### Task 4.1: Commit the OpenAPI document + generate types

**Files:** Add a backend dump script; Modify `packages/shared-types/{package.json,src/index.ts}`, add `src/generated.ts`, `apps/backend/openapi.json`.

- [ ] **Step 1:** Add `apps/backend/scripts/dump_openapi.py` printing `json.dumps(create_app(Settings(app_env="test")).openapi(), indent=2)`; write to `apps/backend/openapi.json`.
- [ ] **Step 2:** `npm run gen -w @restart/shared-types` → `src/generated.ts` from `openapi-typescript`.
- [ ] **Step 3:** Rewrite `src/index.ts` to re-export curated aliases from `generated.ts` (e.g. `export type MonteCarloResponse = components["schemas"]["MonteCarloResponse"]`), preserving the existing import names the frontend uses.
- [ ] **Step 4:** `npm run typecheck` + `vitest` + frontend `next build` → green (frontend imports unchanged).
- [ ] **Step 5:** Commit: `feat(shared-types): generate DTOs from OpenAPI (retire hand-mirroring)`.

### Task 4.2: CI drift gate

**Files:** Modify `scripts/verify.ps1` (+ `.github/workflows/ci.yml` if present).

- [ ] **Step 1:** Add a verify step: dump `openapi.json`, regenerate types, `git diff --exit-code apps/backend/openapi.json packages/shared-types/src/generated.ts`. Non-zero ⇒ fail with "regenerate shared-types".
- [ ] **Step 2:** Run `scripts/verify.ps1` → green. Commit: `ci: fail on OpenAPI/shared-types drift`.

> Update TECHNICAL_DEBT: the two "shared-types hand-mirrored → OpenAPI codegen" rows are now **closed**.

---

## M5 — pitch-kit package

### Task 5.1: Scaffold the workspace

**Files:** Create `packages/pitch-kit/{package.json,tsconfig.json,vitest.config.ts,src/index.ts,src/tokens.css}`.

- [ ] **Step 1:** `package.json` name `@restart/pitch-kit`, peerDeps react/react-dom, deps visx, scripts `typecheck`/`test`. Mirror the frontend's tsconfig/vitest setup.
- [ ] **Step 2:** `tokens.css`: full token scale from doc 07 (surfaces, line, signal green, warn amber, mono/sans, CI-whisker color). Frontend `globals.css` imports it.
- [ ] **Step 3:** `npm install` → workspace resolves. Commit: `feat(pitch-kit): scaffold package + design tokens (doc 07)`.

### Task 5.2: SVG Pitch component (move + generalize existing)

**Files:** Create `packages/pitch-kit/src/Pitch.tsx` + `Pitch.test.tsx`; later delete `apps/frontend/src/components/Pitch.tsx`.

- [ ] **Step 1 (test):** renders a 105×68 SVG with penalty-area geometry; given tracks, renders the right number of player markers; honors `prefers-reduced-motion` (no animation attrs).
- [ ] **Step 2:** Port the existing `Pitch.tsx` rendering into pitch-kit, parameterized by `{attTracks, defTracks, ballPath, times, frame}` (controlled frame for the replay player). Keep snap-to-grid helpers (`snap(v, 0.5)`).
- [ ] **Step 3:** Run vitest → PASS. Commit: `feat(pitch-kit): canonical SVG pitch component`.

### Task 5.3: ReplayPlayer + chart wrappers

**Files:** Create `src/ReplayPlayer.tsx`, `src/charts/{Histogram,Ecdf,KpiCard}.tsx` + tests.

- [ ] **Step 1 (test):** `ReplayPlayer` exposes play/pause + scrubber, steps frames on a fixed cadence, emits `onFrame`; `Histogram`/`Ecdf` render bars/steps for a sample array; `KpiCard` renders `p` with its CI whisker and a "how?" affordance.
- [ ] **Step 2:** Implement as plain SVG (linear scale helpers, `<rect>` bars, `<polyline>` for the ECDF step). Keyboard: space=play/pause, ←/→=scrub (doc 07).
- [ ] **Step 3:** Run vitest → PASS. **verify.ps1 green.** Commit: `feat(pitch-kit): replay player + visx histogram/ECDF/KPI wrappers`.

---

## M6 — Scenario Workbench

### Task 6.1: Expand design tokens + API client

**Files:** Modify `apps/frontend/src/app/globals.css`, `src/lib/api.ts`.

- [ ] **Step 1:** `globals.css` imports `@restart/pitch-kit/tokens.css`; remove the now-duplicated foundation tokens.
- [ ] **Step 2:** `api.ts`: add `teams()`, `players(team)`, `createScenario()`, `createSimRun()`, `getSimRun(id)`, `simRunEvents(id)`, plus a `pollSimRun(id, onProgress)` helper (interval polling until terminal; respects problem-json errors). Send `X-API-Key` when `NEXT_PUBLIC_API_KEY` is set.
- [ ] **Step 3:** `npm run typecheck` green. Commit: `feat(frontend): tokens via pitch-kit + sim-runs polling client`.

### Task 6.2: Scenario library page

**Files:** Create `src/app/scenarios/page.tsx`; Test (vitest) `scenarios.test.tsx`.

- [ ] **Step 1 (test):** renders the canonical seed scenario card + a "New scenario" action; links to `/scenarios/[id]`.
- [ ] **Step 2:** Implement: list canonical WC2026 scenario(s) + any persisted scenarios; empty state teaches (doc 07 "empty states teach").
- [ ] **Step 3:** Run vitest → PASS. Commit: `feat(frontend): scenario library page`.

### Task 6.3: Workbench host with Build/Simulate/Replay modes

**Files:** Create `src/app/scenarios/[id]/page.tsx`, `src/components/workbench/{Build,Simulate,Replay}.tsx`; replace `Workbench.tsx`; Test `Workbench.test.tsx`.

- [ ] **Step 1 (test):** keyboard `B/S/R` switches modes; pre-loaded with a sensible routine vs zonal (empty-state-teaches); the result panel shows `engine v0.4.0 · seed N · n=…` in mono (determinism surfaced); "no winner badge without significance" rule holds in compare.
- [ ] **Step 2 (Build):** real-squad pickers (`api.teams`/`players`), routine + scheme select, and **snap-to-grid constrained handles** for delivery target + key runner zone over the pitch-kit `Pitch` (drag → `snap(0.5m)`; kinematically-infeasible run rendered red per doc 07). Persist via `createScenario`.
- [ ] **Step 3 (Simulate):** launch a sim-run (`createSimRun`), poll progress (progress bar), then render distributions (`Histogram`/`Ecdf` of `xg_samples`) + KPI cards with CI whiskers (`MonteCarloResponse` proportions).
- [ ] **Step 4 (Replay):** `ReplayPlayer` over `Pitch` using `simRunEvents(id, sample=replay)`; event-marked scrubber; sample picker (median/best/worst/random).
- [ ] **Step 5:** Run vitest → PASS. **verify.ps1 green.** Commit: `feat(frontend): Scenario Workbench (Build/Simulate/Replay) on real endpoints`.

> **REVIEW CHECKPOINT 3** — the product is usable by a non-author end to end (local).

---

## M7 — E2E, optional adapters, docs, PR

### Task 7.1: Playwright E2E of the 3-minute journey

**Files:** Create `apps/frontend/playwright.config.ts`, `apps/frontend/tests/e2e/journey.spec.ts`; Modify CI to run it.

- [ ] **Step 1 (test):** the journey — open a scenario → Build (pick squads/routine/scheme) → Simulate at the **reduced budget** (`n_sims=24`) → distributions render with CIs → switch to Replay → scrubber advances. Assert determinism banner shows `seed`/`n`.
- [ ] **Step 2:** `playwright.config.ts` boots the Next dev server + the backend (uvicorn, `RESTART_APP_ENV=test`, in-process queue) as `webServer`s; generous timeout for the ~8 s run.
- [ ] **Step 3:** Run `npx playwright test` locally → PASS. Add a CI job (Playwright browsers cached). Commit: `test(e2e): Playwright 3-minute journey (reduced deterministic budget)`.

### Task 7.2: Postgres loader for marts (drop-in, tested, skipped without PG)

**Files:** Create `packages/etl/src/restart_etl/marts/load_postgres.py`; Modify `cli.py`; Test `packages/etl/tests/test_load_postgres.py`.

- [ ] **Step 1 (test):** marked `@pytest.mark.postgres`, skipped unless `RESTART_TEST_DATABASE_URL` is set; when set, loading a mart twice yields identical row counts (idempotent `DELETE WHERE source=X` + insert in a transaction).
- [ ] **Step 2:** Implement `load_mart_postgres(dsn, table, rows, source_col, source)` using psycopg; transactional delete-by-source + insert. CLI: `restart-etl load-postgres --dsn ... [--marts-dir ...]`.
- [ ] **Step 3:** Run `uv run pytest packages/etl/tests/test_load_postgres.py -v` → SKIPPED (no PG in CI) / PASS locally with PG. Commit: `feat(etl): idempotent Postgres mart loader (drop-in)`.

### Task 7.3: Postgres + Arq runtime adapters (drop-in, tested, skipped without server)

**Files:** Create `repositories/postgres.py`, `jobs/arq_queue.py`; Tests marked + skipped without server; `infra/docker-compose.yml` (pg + redis).

- [ ] **Step 1 (test):** mirror the file-adapter round-trip tests against Postgres (`@pytest.mark.postgres`); an Arq-adapter smoke test marked `@pytest.mark.redis`. Both skip without the env URLs.
- [ ] **Step 2:** Implement the adapters to the same Protocols; selection by settings (`database_url`/`redis_url` present ⇒ use them, else file/in-proc). `readyz` now probes the configured backends (closes the `readyz reports skipped` debt for configured deps).
- [ ] **Step 3:** docker-compose for the PG+Redis path; document `restart-etl load-postgres` + keyed Arq worker startup. Commit: `feat(api): Postgres + Arq drop-in adapters + compose; real readyz probes`.

### Task 7.4: Docs, handoff, changelog, assumptions, tech-debt

**Files:** Create `docs/api/README.md`, `apps/frontend/README.md`; Modify `CHANGELOG.md`, `docs/handoff/*`, `docs/simulation-assumptions.md` index, `docs/development-guide.md` (tech-debt).

- [ ] **Step 1:** `docs/api/README.md`: endpoint reference + worked `curl` examples (scenario → sim-run → poll → events); link `/docs`.
- [ ] **Step 2:** `apps/frontend/README.md`: architecture (pitch-kit, workbench modes, polling client, tokens).
- [ ] **Step 3:** CHANGELOG `Unreleased`: Phase 6 entry. PROJECT_STATUS + PHASE_HANDOFF: P6 shipped, P7 next; ASSUMPTIONS_REGISTER (add any P6 simplifications, e.g. squad-selection rule as a registered assumption); TECHNICAL_DEBT: close shared-types + demo-squads + (configured) readyz rows; **keep** the 🔴 kernel + 🔴 calibration + O-3 rows open with a note that P6 did not touch them.
- [ ] **Step 4:** Update root README screenshots/journey blurb.
- [ ] **Step 5:** **Run `scripts/verify.ps1` → all green.** Commit: `docs: Phase 6 API docs, frontend README, handoff + changelog`.

### Task 7.5: Open PR

- [ ] **Step 1:** Push branch; open PR against `main` summarizing scope, the 5 locked decisions, gates evidence, and the explicitly-carried-forward debt. **Stop for review.**

---

## Self-review — spec coverage

| Roadmap / task deliverable | Covered by |
|---|---|
| FastAPI validation + bounds | 1.2 |
| Rate limiting | 1.3 |
| API keys | 1.4 |
| Problem-details errors | 1.1 |
| OpenAPI | 1.5 |
| Arq worker + job progress | 3.3 (in-proc default), 7.3 (Arq) |
| Idempotency keys | 3.1, 3.4 |
| Postgres loaders for marts (idempotent DELETE-WHERE-source) | 7.2 |
| Scenario/routine storage | 2.2, 3.4 |
| Real squads from mart_players/attributes (retire demo) | 2.1, 2.3 |
| Custom routines + async jobs | 3.4 |
| pitch-kit (SVG pitch, replay, charts) | 5.2, 5.3 |
| Scenario Workbench (Build/Simulate/Replay) | 6.3 |
| Scenario library | 6.2 |
| Design tokens per doc 07 | 5.1, 6.1 |
| Playwright E2E (build→1k→distributions→replay) | 7.1 (reduced budget, documented) |
| shared-types kept in sync (OpenAPI codegen) | 4.1, 4.2 |
| Acceptance: oversized n_sims / OOB coords rejected | 1.2 |
| Pure-domain preserved | 2.1 (adapter reads, pure Team out); ports keep IO out of core |
| Determinism surfaced by API | 3.1, 3.2 (same seed ⇒ same result); 6.3 (banner) |
| `ENGINE_VERSION` unchanged | global constraint; no engine file touched |
| Carried-forward debt NOT absorbed | 0.4 ADR + 7.4 tech-debt notes |

**Open risks flagged for review:** (a) E2E uses `n_sims=24` not 1000 — documented throughput compromise; (b) squad-selection rule is a new registered assumption (priors may dominate — links to R9); (c) Postgres/Arq adapters are tested-but-CI-skipped without servers (the file-first decision's accepted trade-off).

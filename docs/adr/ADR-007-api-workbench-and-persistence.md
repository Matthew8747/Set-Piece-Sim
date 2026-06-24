# ADR-007 - API & Scenario Workbench: ports-and-adapters, async jobs, real squads

**Status:** Accepted · **Date:** 2026-06-15 · **Phase:** 6
**Related:** design doc 02 (system architecture §4-§9, API surface), design doc 07 (UI/UX),
design doc 08 (roadmap Phase 6), ADR-005 (data platform / injected-port precedent),
ADR-006 (`restart_opt` stays out of the API runtime), ENGINE_VERSION `sim/0.4.0` (unchanged)

## Context

Phase 6 makes the platform usable by a non-author: a hardened FastAPI surface, asynchronous
Monte Carlo with progress, persisted scenarios, **real squads** drawn from the marts (replacing
demo squads), and a Scenario Workbench (Build / Simulate / Replay). Three forces shape the
execution. The **pure-domain rule** (`restart` imports no web/DB/ML/IO) means every piece of
infrastructure must live in the `restart_api` adapter, never the core. The **throughput reality**
(reference engine ≈ 3 sims/s, measured in P5) means a 1k-sim run takes ~5.5 min - synchronous
requests would block and CI cannot run a real 1k-sim batch. The **server-free CI value** (the
file-based DuckDB warehouse keeps CI dependency-free, per the P4 loader) must survive the
introduction of Postgres and a job queue. The product design is fixed in docs 02 and 07; this ADR
records the execution decisions.

## Decisions

1. **Ports-and-adapters with a file-first default.** Persistence and job execution are expressed as
   Protocols in the `restart_api` adapter (`TeamRepository`, `ScenarioRepository`,
   `SimRunRepository`, `JobQueue`). The **default** adapters are server-free: squads/marts read from
   the committed Parquet, scenarios and sim-runs persist to a SQLite file, and jobs run in an
   in-process asyncio worker. **Postgres** and **Arq/Redis** adapters implement the same Protocols as
   drop-ins, selected at runtime when `RESTART_DATABASE_URL` / `RESTART_REDIS_URL` are set. This keeps
   CI and local dev dependency-free while shipping (and testing, against an opt-in server) the
   production path. It mirrors the injected-`XGScorer` precedent from ADR-005. The Postgres mart
   loader is added to `restart_etl` (already an IO package) as the idempotent `DELETE WHERE source=X`
   + insert drop-in beside the DuckDB loader.

2. **Real squads from the marts; demo squads retired from the API runtime.** A `MartSquadLoader` in
   the adapter reads `mart_players` + `mart_player_attributes` (committed, provenance-tagged,
   StatsBomb-derived - no scraped ratings) and emits a **pure** `restart.players.Team`. The pure core
   never reads files; the adapter does the reading and hands the core plain domain objects. Selection
   of an XI from the multi-match player pool is a fixed, deterministic rule (1 GK by appearances +
   a 4/4/2 outfield quota ranked by `heading + delivery`, all ties broken by `player_id`), registered
   as a new simulation assumption because attribute priors can dominate outcomes (links risk R9).
   Demo squads remain only as licensing-safe synthetic *test fixtures* for the core.

3. **Asynchronous Monte Carlo as a job, with idempotency by scenario hash.** `POST /sim-runs`
   enqueues a job and returns `202` + a run id; the client polls `GET /sim-runs/{id}` for
   status/progress and the aggregate result. The idempotency key is the canonical-JSON SHA-256 of the
   scenario spec folded with `seed` and `engine_version` (design doc 02 §4.1/§6); a duplicate key
   returns the existing run rather than recomputing - which also *guarantees* the determinism contract
   (same seed ⇒ same surfaced result). The in-process worker chunks the batch to report monotonic
   progress and collects a bounded, deterministically-sampled set of per-sim xG values for the
   distribution charts.

4. **Progress by polling, not SSE.** Roadmap-settled (doc 08 Phase 6: "polling first, SSE only if UX
   demands"). Reversible - the client has a single `pollSimRun` seam.

5. **RFC 9457 problem-details for all errors.** Domain exceptions and validation failures map to
   `application/problem+json` (`type`/`title`/`status`/`detail`/`instance`), documented in OpenAPI.
   Writes require an API key when one is configured; with no key the deployment is demo-mode
   (reads + bounded sim sizes), per the security checklist (doc 02 §9). Per-IP rate limiting
   (slowapi; in-memory default, Redis when configured) plus a global concurrent-job cap protect the
   demo from cost-bombing.

6. **shared-types generated from OpenAPI.** `openapi-typescript` generates `@restart/shared-types`
   from the committed `openapi.json`; CI fails on drift. This retires the hand-mirroring tech-debt now
   that the surface roughly triples.

7. **Charts hand-rolled as SVG (deviation from doc 07's visx).** visx 3.x peers cap at React 18 and
   the app is React 19 (hard `ERESOLVE`); no React-19-compatible visx release exists. Rather than
   loosen peer resolution repo-wide, the histogram / ECDF / KPI-CI-whisker primitives - all simple -
   are hand-rolled as plain SVG in `pitch-kit`. This honors doc 07's stated intent ("custom SVG,
   React owns the DOM, not a charting template") and drops a blocked dependency.

## Consequences

- `ENGINE_VERSION` is **unchanged** (`sim/0.4.0`): Phase 6 touches no engine behaviour.
- CI stays server-free; the Postgres/Arq adapter tests are marked and **skipped** unless
  `RESTART_TEST_DATABASE_URL` / a Redis URL is provided - the accepted trade-off of the file-first
  decision. A `docker compose` file documents the server path.
- The Playwright E2E runs the journey at a **reduced, deterministic budget** (`n_sims=24`, ≈ 8 s) over
  the identical build → run → distributions → replay path; the full bounded range remains available
  for real use. The throughput compromise is documented, not hidden.
- The squad-selection rule is a registered assumption; if attribute priors prove to dominate, the
  product reports routine *classes* rather than precise winners (the R9 mitigation already on file).

## Explicitly NOT in scope (carried forward, not absorbed by Phase 6)

- **Fused Numba scenario kernel (🔴, ADR-003 d8)** - still the path to 10⁵-10⁶-sim studies; Phase 6
  does not touch it.
- **Engine upstream `[knob]` calibration (🔴, owed since P3/P4)** - the simulated shot-context
  distribution remains unvalidated; untouched here.
- **First-contact-only engine fidelity (O-3)** - multi-touch pass-then-shot, shoot-vs-pass lookahead,
  and defender anticipation remain FUTURE ENGINE phases (doc 05 §8), not Phase 6.

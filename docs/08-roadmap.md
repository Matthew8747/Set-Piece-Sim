# 12-Week Development Roadmap - Restart Lab

**Version:** 0.1 · **Status:** Design review draft

Sequencing principle: **vertical slice, corners first.** From Phase 3 (week 5) onward the project
is permanently demoable; every later phase upgrades a working system. Free kicks/throw-ins and 3D
are scheduled stretch (Tier 2), pulled in only if their phase's gate passes early.

Working assumption: one developer, ~15-20 focused hours/week. Phases own calendar weeks; slack
is explicit (Phase 8 is half buffer).

---

## Phase 0 - Foundations & data audit (Week 1)

**Goals:** Running skeleton; licensing certainty; design package ratified.
**Deliverables:** Monorepo scaffold (backend package layout, Next.js app, Compose with
pg/redis); CI (lint=ruff, type=mypy+tsc, test=pytest/vitest on every PR); StatsBomb ingestion
spike (one tournament fetched, corner counts + freeze-frame coverage measured); signed-off
licensing memo; pinned calibration-target bands (with citations) in
`docs/simulation-assumptions.md` (seeded from design doc 05).
**Architecture decisions:** import-linter contracts enacted; pre-commit hooks; UUIDv7 + Alembic
baseline migration.
**Risks:** Freeze-frame coverage for set pieces lower than assumed → *measured this week by
design*; if < ~800 usable corner shot events across tournaments, xG features degrade gracefully
(drop traffic features, keep geometry - decision recorded).
**Alternatives considered:** Poetry vs uv (choose **uv** - speed, lockfile, 2026 default);
monorepo vs two repos (mono - atomic doc+code changes).
**Documentation required:** Root README v1; CONTRIBUTING.md (solo project, but defines PR/CI
discipline); licensing memo; this package committed.
**Acceptance criteria:** `docker compose up` + `make test` green in CI from clean clone;
data spike notebook committed with measured counts; all 8 design docs reviewed.

## Phase 1 - Physics core (Weeks 2-3)

**Goals:** Trustworthy ball physics, validated and benchmarked.
**Deliverables:** `restart.physics` (RK4 flight w/ drag+Magnus, bounce/roll, contact-impulse
resolution w/ skill noise hooks); golden + property test suites; validation notebook V1
(drag-free analytic match, literature drag/Magnus comparison, Roberto Carlos recreation);
vectorized batch ball-stepping (the `(n_sims, …)` tensor layout proven here, *before* agents
exist); benchmark harness in CI.
**Architecture decisions:** fixed dt=5 ms ball / 20 ms agents; SoA tensor layout (commit);
units = SI everywhere, enforced by a thin `domain.units` layer.
**Risks:** Vectorized + readable + correct is genuinely hard → mitigate by writing the scalar
reference implementation first, then the vectorized one, with equivalence tests between them
(the scalar version remains as documentation and debugging tool).
**Alternatives considered:** scipy `solve_ivp` (rejected: adaptive stepping breaks lockstep
batching); JAX (re-checked, still rejected for v1).
**Documentation required:** `simulation-assumptions.md` sections P-1..P-13 finalized with
citations.
**Acceptance criteria:** All V1 validation checks pass with pinned tolerances; batch of 10k
ball-only flights < 1 s single-core; equivalence scalar↔vectorized within 1e-9.

## Phase 2 - Agents & tactical engine (Weeks 3-4)

**Goals:** A complete corner plays out headlessly with believable movement.
**Deliverables:** `restart.agents` (kinematic envelopes, reaction latency, interception solver,
jump/contest entry, soft-disc separation); `restart.tactics` (Routine Spec `rs/1.0` schema +
validation, defensive scheme templates: zonal/man/hybrid, `compile()` → SimProgram); 5 library
corner routines + 3 schemes; debug renderer (matplotlib animation - throwaway by design, the
real replay UI comes in Phase 6); free-kick feasibility spike (1 day: confirm Routine Spec
expresses a wall + direct FK without schema surgery - validates PRD `A-3` early).
**Architecture decisions:** two-layer decision model (scripted intents + reactive interception)
(commit); contest resolution via softmax scoring (commit - the calibration interface).
**Risks:** *The* behavioral-realism risk concentrates here (orbiting runs, zombie defenders).
Mitigate: V2 kinematic gates + a face-validity checklist run on every library routine; timebox
behavior polish, log defects for calibration phase rather than gold-plating now.
**Alternatives considered:** behavior trees library (rejected: roles are simple enough that a
plain state machine per role is more debuggable); continuous re-planning every tick (rejected:
reaction latency is both more realistic and cheaper).
**Documentation required:** G-1..G-7 assumptions finalized; Routine Spec schema doc (JSON Schema
+ annotated example - this doubles as API documentation later).
**Acceptance criteria:** 10 scripted corners run start-to-terminal with zero kinematic-invariant
violations (property suite); debug animations of 5 library routines pass face-validity checklist;
free-kick spike memo concludes "configuration, not construction" (or escalates).

## Phase 3 - Monte Carlo & calibration v1 (Week 5) - **the credibility gate**

**Goals:** 10k-run batches with statistics; simulated rates inside real-world bands.
**Deliverables:** `restart.montecarlo` (masked phase ticking, Philox child streams, chunking,
event-log extraction, Wilson/bootstrap CIs, common-random-numbers support); calibration harness
(grid/TPE over the ≤ 8 named knobs vs pinned bands); calibration report v1 (before/after tables,
held-out check vs Euro 2024 rates); quarantine machinery.
**Architecture decisions:** screen-then-confirm statistics policy (commit); event-log schema
(commit - replay + analytics contract).
**Risks:** **Calibration may not converge into bands** - the existential risk, surfaced
deliberately in week 5 of 12. Contingency ladder: (1) widen acceptable bands with justification,
(2) add one knob with documented rationale, (3) re-scope claims from "predictive rates" to
"comparative analysis under a calibrated-order-of-magnitude model" - the product survives all
three rungs; the writeup reports which rung we landed on.
**Alternatives considered:** ABC/simulation-based inference for calibration (rejected:
fascinating, unjustifiable on schedule; noted as future work).
**Documentation required:** M-1..M-3 finalized; calibration methodology + results in
`simulation-assumptions.md`.
**Acceptance criteria:** 10k corner sims < 60 s / 4 cores (CI benchmark); goal/shot/
first-contact rates within pinned bands on calibration set AND within 1.5× band width on
held-out set; determinism test (same seed ⇒ identical event logs) green.

## Phase 4 - Data platform, profiles & xG v1 (Week 6)

**Goals:** Real data flowing; xG layer live; 6-8 national teams usable.
**Deliverables:** `etl` package (raw→staging→marts per design doc 04, quality gates in CI);
`mart_setpiece_shots` populated; attribute derivation per doc 04 §3 for the launch teams;
System-A xG models (LR baseline + GBM sweep, grouped CV, calibration analysis); model cards;
MLflow wiring; simulator integration (sim emits shot contexts → active model scores).
**Architecture decisions:** xg-header + xg-foot two-model split (reversible, learning-curve
dependent); active-model pinning via `ml_models.is_active`.
**Risks:** Set-piece shot sample size → measured in Phase 0, feature plan degrades gracefully;
attribute priors dominating outcomes → sensitivity analysis scheduled Phase 5.
**Alternatives considered:** per design docs 04 §7 and 06 §2.2.
**Documentation required:** Data dictionary v1 (CI-checked); model cards; ETL runbook
(`restart-etl all` from clean clone).
**Acceptance criteria:** ETL rebuild from raw cache < 10 min, quality gates green; GBM vs LR
decision recorded with held-out calibration evidence (slope 0.9-1.1 for the shipped model);
end-to-end: corner batch reports mean xG scored by the real-data model.

## Phase 5 - Optimization engine (Weeks 7-8)

**Goals:** The platform *discovers* routines and explains them.
**Deliverables:** System-B (Optuna TPE over Routine Spec sub-space; random-search baseline at
equal budget; screen-then-confirm pipeline; anti-exploit flagging); study persistence
(`optimization_studies/trials`); surrogate + SHAP insights generator; attribute sensitivity
analysis (doc 04 §3 guardrail); canonical study: *England corners vs Argentina zonal*.
**Architecture decisions:** trial = 500-sim screen, top-5 confirm at 10k with CRN (commit);
objective = mean xG with counterattack-risk reported (not yet optimized - multi-objective is
future work, documented).
**Risks:** Optimizer exploits sim artifacts → anti-exploit rules + face-validity review of top-5
(scheduled, not incidental); TPE underperforms on the categorical-heavy space → random-search
baseline catches this honestly; budget overruns → studies are resumable by design.
**Alternatives considered:** full matrix in design doc 06 §3.2 (CMA-ES/GA = Tier-2 comparison
study if week 8 has slack).
**Documentation required:** Optimization methodology doc; canonical study writeup (becomes the
case-study centerpiece).
**Acceptance criteria:** TPE beats random search at equal budget (significant difference in
best-found confirmed xG); top routine beats library baseline with non-overlapping 95% CIs;
SHAP insights panel renders ≥ 3 plain-language findings a coach could act on; sensitivity
analysis conclusion recorded.

## Phase 6 - API & Scenario Workbench (Weeks 9-10)

**Goals:** The product becomes usable by a non-author.
**Deliverables:** FastAPI surface (design doc 02 §5: validation, rate limiting, API keys,
problem-details errors, OpenAPI); Arq worker + progress; idempotency; `pitch-kit` (SVG pitch,
replay player, chart wrappers); Scenario Workbench (Build/Simulate/Replay), scenario library;
Playwright E2E of the 3-minute journey; design tokens per doc 07.
**Architecture decisions:** replay JSON format shared 2D/3D (commit); polling first, SSE only
if UX demands (reversible).
**Risks:** Frontend scope explosion - the workbench is 80% of UI value, everything else in
Phase 7 is cuttable; pitch-editor interaction polish is a time sink → snap-to-grid + constrained
handles over free-form gestures.
**Alternatives considered:** per design doc 07 §6.
**Documentation required:** API documentation (OpenAPI + worked `curl` examples); frontend
architecture README; updated screenshots in root README.
**Acceptance criteria:** E2E green in CI (build → 1k run → distributions → replay); a
non-author user completes the journey unaided < 3 min (hallway test, n≥2); rate limits and
input bounds verified by tests (oversized n_sims, out-of-bounds coordinates rejected).

## Phase 7 - Intelligence surfaces & Tier-2 stretch (Week 11)

**Goals:** The "platform" feel: comparisons, reports, insights; stretch content if gates passed.
**Deliverables (priority order, cut from bottom):** Team Intelligence + mismatch matrix;
nation-vs-nation comparison; exportable report page (print CSS); optimization UI (convergence,
parallel-coords, insights panel); models/methods pages; **stretch:** free kicks (direct +
crossed) using Phase-2 spike result; long throw-ins; **3D replay (R3F, camera presets) - static
player markers + the ball's full 3-D flight (z) for a single sim *and* the best-found optimized
routine** (animation optional; the ball trajectory is the point).
**Architecture decisions:** reports = server-rendered pages with print CSS (commit, no PDF lib).
**Risks:** Stretch greed - rule: nothing from the stretch list starts unless every Tier-1 item
above it is at acceptance; 3D is explicitly the *last* pull.
**Alternatives considered:** PDF generation libs (rejected, print CSS); separate marketing
site (rejected, landing page suffices).
**Documentation required:** Report methodology footnotes (every number traceable); user-facing
methods page content.
**Acceptance criteria:** England-vs-Argentina report exports clean A4; comparison view enforces
same-engine-version rule; if stretch pulled: free-kick scenario passes the same calibration
sanity + face-validity gates as corners (gate, not vibes).

## Phase 8 - Hardening, deployment & case study (Week 12, ~50% buffer)

**Goals:** Live, secure, documented, told well.
**Deliverables:** Deployment (Vercel web + Railway/Fly api/worker/pg/redis; Compose parity);
security checklist (doc 02 §9) executed and evidenced; precomputed canonical scenarios (demo
never depends on cold heavy compute); Sentry + uptime check; load sanity test (10 concurrent
users on demo path); **portfolio case study** (problem → architecture → calibration honesty →
optimization findings → screenshots → "what I'd do with 6 more months"); README final; demo
video (2-3 min screen capture).
**Architecture decisions:** demo mode = read-everything + bounded interactive sims (≤ 1k) +
keyed full access (commit).
**Risks:** Buffer consumed by earlier slips - that is its job; the case study is written from
per-phase notes (15 min/week discipline), not from memory in week 12.
**Alternatives considered:** all-Vercel deploy (re-evaluated once at deploy time - if worker
fits fluid-compute limits comfortably, simpler ops wins) **(reversible)**.
**Documentation required:** Deployment guide (clean-machine reproduction); final docs pass
(stale-link/stale-claim sweep); model cards current.
**Acceptance criteria:** Cold visitor on a phone completes the 3-minute journey on the live
URL; security checklist 100% evidenced; case study reviewed by one outside reader; clean-clone
`docker compose up` reproduces the platform with seeded demo data.

---

## Milestone summary

| Week | Gate |
|---|---|
| 1 | Design ratified; data audit done; CI green |
| 3 | Ball physics validated (V1) |
| 4 | Full corner plays out headlessly (V2); FK feasibility confirmed |
| **5** | **Calibration v1 inside bands (V3) - go/no-go on predictive claims** |
| 6 | Real data + xG live end-to-end |
| 8 | Optimizer beats baselines with significance; insights generated |
| 10 | Workbench usable by a stranger |
| 11 | Reports + comparisons; stretch content if earned |
| 12 | Live demo + case study shipped |

## Risk register (consolidated)

| # | Risk | L | I | Mitigation | Phase |
|---|------|---|---|------------|-------|
| R1 | Calibration fails bands | M | **H** | Contingency ladder (P3); honest re-scoping rung | 3 |
| R2 | Scope explosion | **H** | H | Tiering, per-phase cut lines, stretch rules | all |
| R3 | Behavioral uncanny valley | M | M | V2/V4 gates, face-validity checklist, debug renderer early | 2-3 |
| R4 | Set-piece data sparsity | M | M | Phase-0 measurement; graceful feature degradation | 0, 4 |
| R5 | Licensing misstep | L | **H** | Phase-0 memo; mechanical CI license gate; no scraped ratings | 0+ |
| R6 | Perf misses 100k budget | L | M | SoA design from Phase 1; CI benchmarks; chunking; Numba reserve | 1, 3 |
| R7 | Optimizer exploits sim bugs | M | M | Anti-exploit flags + face-validity review of winners | 5 |
| R8 | Solo bandwidth / life | M | M | Vertical slice = always shippable; Phase-8 buffer | all |
| R9 | Attribute priors dominate results | M | M | Sensitivity analysis; report routine *classes* if unstable | 4-5 |
| R10 | First-contact-only engine caps routine realism (no pass-then-shot combos, no shoot-vs-pass lookahead, no defender anticipation) | **H** | M | Registered fidelity cut (O-3); scoped as future engine work (doc 05 §8), to land with/after the Numba kernel | future |

## Documentation roadmap (PRD-required artifacts → where produced)

README (P0, final P8) · Architecture (this package, living) · Tech spec (docs 02-06, living) ·
Data dictionary (P4) · API docs (P6) · Simulation assumptions (P1-P3) · Model cards (P4-P5) ·
Deployment guide (P8) · Contributor guide (P0) · Case study (P8, notes weekly).

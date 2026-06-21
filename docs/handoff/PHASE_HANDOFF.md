# Phase Handoff

> Rewritten at the end of every completed phase.

## Last completed phase: Phase 7 — Optimization UI & 3D replay (`/optimize`, R3F replay, CRN compare)

### What shipped

- **Read-only optimization API** — a `StudyLoader` parses the committed
  `optimization_studies/<slug>/study.json` into typed DTOs and serves
  `GET /api/v1/optimizations` (summaries) + `/{id}` (detail: trials, best-so-far convergence,
  parallel-coords axis metadata, top-k confirm vs baseline, SHAP `feature_importance`, plain-language
  `insights`, sensitivity verdict, winner + anti-exploit flags). `restart_opt` (Optuna / LightGBM /
  SHAP) is **never imported** in the request path — a guard test asserts it stays out of `sys.modules`
  ([ADR-008](../adr/ADR-008-optimization-surface-and-3d-replay.md), extends ADR-006). Studies whose
  `engine_version` ≠ runtime are flagged `stale`.
- **pitch-kit optimization primitives** (hand-rolled SVG, React-19, no visx) — `ConvergencePlot`
  (best-so-far TPE vs equal-budget random + winner CI band + library-baseline ref),
  `ParallelCoordinates` (the search-space view; `normAxis` ladders mixed continuous/categorical axes,
  ordered by SHAP importance), `TopKTable` (a beats-baseline marker only on non-overlapping CIs).
- **`/optimize` + `/optimize/:id`** — study library (beats-baseline badge only when significant) and a
  detail page composing the primitives + a SHAP insights panel + a sensitivity honesty banner
  (reports routine *classes* when the ranking flips under ±10% — the canonical study does).
- **Workbench compare mode (`C`)** — two scenarios run at the same seed + n_sims are paired by the
  montecarlo determinism contract (CRN); `compareStats` (pure, tested) returns the mean paired
  difference + 95% CI; a winner shows **only when the CI excludes zero** (doc 07 §4 stats policy);
  distributions overlay on a shared x-scale (new `Histogram` `domain` prop).
- **On-demand 3D replay (R3F)** — `Replay3D` consumes the **same** `SimulateResponse` as the 2D player
  (`ball_path` z → real flight arc; tracks on the ground plane); camera presets
  (broadcast / behind-goal / GK); `prefers-reduced-motion` freezes on contact. `next/dynamic`
  (`ssr:false`) keeps `@react-three/fiber` + `three` in a lazy chunk; 2D stays the default + SVG-only
  fallback. New deps in the **frontend workspace only**.
- Docs: ADR-008, CHANGELOG Phase-7 entry, this handoff, status/debt registers updated.
  `ENGINE_VERSION` **unchanged** (`sim/0.4.0`).

### Validation evidence

All `scripts/verify.ps1` gates green (ruff, black, mypy --strict, pytest, next build, eslint, tsc on
all three workspaces, vitest, prettier, OpenAPI/shared-types drift). pitch-kit: 20 vitest;
frontend: 24 vitest (incl. `compareStats`, `replay3d-util`, `/optimize` components, compare badge).
Backend optimization surface: 11 pytest (loader, derivations, endpoints, 404, `restart_opt`-not-imported
boundary). The full Python suite is unchanged from P6 green — Phase 7 added one backend module
(`restart_api.studies`) and no engine code.

### Debugging history worth knowing (saves future sessions time)

1. **`winner.ci` in `study.json` is `[mean, lo, hi]`** (not `[lo, hi]`). The convergence band maps the
   last two; the summary reads index 0 as the headline mean.
2. **React-compiler ESLint flags impure calls during render.** `useRef(performance.now())` fails
   "Cannot call impure function during render" — stamp the start time lazily on the first `useFrame`.
3. **jsdom has no `window.matchMedia`.** `ReplayPanel`'s reduced-motion effect must guard
   `typeof window.matchMedia !== "function"` or the workbench's replay-mode test throws.
4. **R3F v9 + three are heavy** — the dynamic import is load-bearing: a static import would put three.js
   in the default chunk. The build confirms three lands in one lazy chunk only.
5. **`verify.ps1` via the PS-5.1 tool wrapper trips on native stderr** (`uv sync` writes to stderr →
   NativeCommandError under `$ErrorActionPreference=Stop`). Run the gate steps individually, or in a
   real terminal, when the wrapper aborts at step 1.

### Open decisions carried forward (NOT touched by Phase 7)

- **Engine `[knob]` calibration (🔴)** — simulated shot-context distribution still unvalidated
  (goal ~5% sim vs 2–3% real).
- **Fused Numba scenario kernel (🔴)** — gates 10⁵–10⁶-sim studies; **a hard dependency for any
  evolutionary search at real budget**.
- **First-contact-only fidelity (O-3)** — no multi-touch / off-ball / lookahead / defender
  anticipation.
- **Team-intelligence (`/teams`)** + report-export — deferred to Phase 7.x.

## Next phase: Phase 8 — Scenario realism (engine; **bumps ENGINE_VERSION**)

The first engine change since P4, driven by review feedback that replays show too many defenders vs
too few attackers and too little routine variance.

Scope (to be brainstormed + ADR'd before coding — this is engine core, not UI):

1. **Widen the corner genome (O-2).** Today: taker + 4 runners (`restart.optimize.genome.n_runners=4`)
   against a full defensive scheme. Add attacker slots (target 7+) with **off-ball / non-box roles**
   (not every attacker contests the header); widen delivery + run-timing bounds for real variance.
2. **Structured defensive defaults.** Schemes (`restart.tactics`) gain a sensible base structure —
   e.g. a near-post man for most scenarios, a defensive line — instead of purely reactive marking.
3. **Determinism + calibration discipline.** Bump `ENGINE_VERSION` (`sim/0.5.0`); re-baseline the
   committed study only after the change is validated; do **not** silently absorb the 🔴 calibration
   or 🔴 kernel debt — those remain their own phases.

### Risks for Phase 8
1. Bumping `ENGINE_VERSION` invalidates the committed `study.json` (it will read `stale` in `/optimize`
   until regenerated) — sequence the regen, and keep the read-only surface tolerant of stale studies
   (it already is).
2. More attackers + wider bounds = more sims at ~3 sims/s — throughput pressure makes the 🔴 Numba
   kernel more urgent; scope budgets honestly (ADR-006) until it lands.
3. Free kicks (offside, off-ball runners) and evolutionary search (GA + lineage viz) are **separate
   later phases**, not Phase 8 — keep scope contained to the corner template + defensive structure.

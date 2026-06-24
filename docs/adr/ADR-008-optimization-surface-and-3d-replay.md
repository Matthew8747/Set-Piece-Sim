# ADR-008 - Read-only optimization surface, CRN compare, and on-demand 3D replay

**Status:** Accepted · **Date:** 2026-06-20 · **Phase:** 7
**Related:** design doc 07 (UI/UX - `/optimize` IA, compare-mode stats policy §4, 3D camera presets),
design doc 09 (optimization methodology), ADR-006 (`restart_opt` stays out of the API runtime -
this ADR extends it), ADR-007 (API/workbench, hand-rolled SVG charts d7), ENGINE_VERSION `sim/0.4.0`
(unchanged - this is a UI/read-API phase).

## Context

Phase 7 turns the persisted optimizer study into a coach-facing surface, adds the common-random-number
compare mode to the workbench, and adds an optional 3D replay. Three forces shape the execution. The
**`restart_opt`-out-of-runtime rule** (ADR-006: Optuna / LightGBM / SHAP / MLflow never enter a
request) means the optimization surface must read the persisted `study.json` as *data*, never run a
search. The **honesty bar** (doc 07 §4 / Simulation-Architecture §5.4: no winner without significance)
must be enforced in code, not left to a label. The **bundle discipline** (doc 07 §5: R3F is Tier-2,
load-on-demand) means three.js must never enter the default chunk. The product design is fixed in
docs 07 and 09; this ADR records the execution decisions.

## Decisions

1. **The optimization surface is data, not compute (extends ADR-006).** A `StudyLoader` in
   `restart_api` parses `optimization_studies/<slug>/study.json` into typed DTOs
   (`OptimizationSummaryDTO` / `OptimizationDetailDTO`) and serves them at `GET /api/v1/optimizations`
   and `/{id}`. Derivations the UI needs but the artifact does not store - the cumulative-max
   best-so-far convergence series, and the parallel-coordinates axis metadata (continuous domain vs
   categorical order, ordered by SHAP importance) - are pure module-level functions, unit-tested. A
   guard test asserts that importing the app never pulls `restart_opt` (or any submodule) into
   `sys.modules`: the optimizer's home is the offline CLI, and the runtime boundary is now executable,
   not just documented. Studies whose `engine_version` differs from the running `ENGINE_VERSION` are
   flagged `stale` (surfaced, never a failure).

2. **Charts stay hand-rolled SVG (re-affirms ADR-007 d7).** The convergence plot (best-so-far TPE vs
   the equal-budget random baseline, the library-baseline reference line, the winner's CI band),
   the parallel-coordinates "wow" view, and the top-k table are plain SVG primitives in
   `@restart/pitch-kit`. visx still caps its peer deps at React 18; the app is React 19. The only
   exception remains React Three Fiber, for 3D.

3. **Compare mode is honest by construction (doc 07 §4).** Two scenarios are run through the existing
   `/sim-runs` at the **same seed and n_sims**. The montecarlo determinism contract
   (`sim_seeds(root_seed, n)` is scenario-independent) then guarantees sim *i* of each scenario sees
   the identical per-sim seed - so the per-sim xG vectors are **paired** (common random numbers) with
   no new simulation compute. A pure `compareStats` function returns the mean paired difference and a
   large-sample 95% CI; the UI shows a winner **only when that CI excludes zero**, otherwise "no
   significant difference". Sharing one set of inputs for both runs makes the same-seed/same-n
   requirement structural rather than a checkbox. The two distributions render on a **shared x-scale**
   (a new optional `domain` prop on the histogram) so the difference is read off one axis, not two.

4. **3D replay consumes the existing replay JSON, loaded on demand.** `Replay3D` (R3F) reads the same
   `SimulateResponse` the 2D `ReplayPlayer` uses: `ball_path` carries z, so the flight arc is real;
   the 2D player tracks sit on the ground plane. Camera presets are broadcast / behind-goal / GK;
   `prefers-reduced-motion` freezes the scene on the contact frame. The component is imported via
   `next/dynamic` (`ssr:false`), so `@react-three/fiber` + `three` live in a lazy chunk and never the
   default bundle (verified in the build output). **2D stays the default and the SVG-only fallback.**
   These deps are added to the **frontend workspace only** - pitch-kit (a shared, dependency-light
   package) does not take a three.js dependency.

## Consequences

- The whole optimization contract flows through the OpenAPI schema → shared-types codegen → the
  `verify.ps1` drift gate, the same as the rest of the API.
- "Winner" language is bounded the same way the methodology bounds it: with the carried 🔴 calibration
  unresolved and the canonical study's ranking flipping under ±10% attribute perturbation, the detail
  page reports routine **classes** (the sensitivity banner), and the compare badge never appears
  without a significant paired-difference CI.
- 3D is purely additive: it reads the existing transport, ships in a lazy chunk, and degrades to 2D.

## Explicitly NOT in scope (deferred)

- **Team-intelligence (`/teams`)** - squad aerial/pace profiles, mismatch matrix - deferred to a
  Phase 7.x follow-up (the doc 07 IA item budgeted "if budget allows").
- **Running any optimizer search from the browser**, or generating new studies - remains a CLI/offline
  concern (ADR-006).
- **Carried-forward 🔴 debt** (engine `[knob]` calibration, fused Numba kernel) and O-3 first-contact
  fidelity - future engine phases; untouched here. (Phase 8 - scenario realism - is the next of these.)

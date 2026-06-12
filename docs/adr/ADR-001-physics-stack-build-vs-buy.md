# ADR-001 — Physics & simulation stack: build vs buy

**Status:** Accepted · **Date:** 2026-06-12 · **Phase:** 1
**Decision owners:** Lead Engineer · **Supersedes:** —

## Context

Phase 1 needs ball-flight physics (gravity, quadratic drag with drag crisis, Magnus, bounce,
spin decay) executing at ≥ 500 sims/s/core in batches up to 100k, deterministic, explainable,
Windows-friendly, and Numba-accelerable later. Directive: prefer mature libraries wherever they
provide equivalent functionality; keep football-specific logic as project IP.

## The shape of the problem (what makes the decision)

A set-piece ball flight is **one point mass under three smooth forces for ~2–4 seconds**, run
**tens of thousands of times independently**. That profile has two consequences:

1. The *hard* part is not rigid-body dynamics — it is the **aerodynamic model** (speed-dependent
   C_d across the drag crisis, spin-dependent Magnus lift). General physics engines do not ship
   aerodynamics; we would hand-write exactly the difficult 20% and inherit an engine for the
   trivial 80% (gravity + one ground contact).
2. The throughput requirement is met by **batch vectorization across sims**, not by a faster
   single-world engine. Engines step one world at a time; NumPy steps 10,000 at once.

## Assessment per candidate

### NumPy — ADOPT (batch numerics foundation)
- **Reason:** Structure-of-arrays batch state `(n_sims, 9)` stepped in lockstep is the only
  design that meets the Monte Carlo budget in Python. Already a dependency.
- **License:** BSD-3 — no constraints. · **Performance:** vectorized C loops; the benchmark
  suite (Phase 1) pins throughput. · **Maintenance:** the most-maintained package in scientific
  Python. · **Portfolio:** expected baseline competency; the *vectorization design* on top of it
  is the showcase.

### SciPy — ADOPT (validation oracle + statistics; not the production integrator)
- **Reason:** `solve_ivp` (DOP853, rtol=1e-10) is an independent, adaptive, high-order
  integrator — the perfect *cross-check oracle* for our fixed-step RK4 in CI. Later phases use
  `scipy.stats` (`binomtest.proportion_ci(method="wilson")`, `bootstrap` with BCa) instead of
  hand-rolled statistics.
- **Why not as the production integrator:** adaptive stepping is per-trajectory — it breaks
  batch lockstep and is ~100× slower per sim through Python callbacks. Wrong tool for the hot
  path, ideal for ground truth.
- **License:** BSD-3. · **Performance:** cold-path only. · **Maintenance:** core ecosystem.
  · **Portfolio:** "custom integrator validated against SciPy DOP853 to < 1 cm over 40 m" is a
  strong credibility line.

### Numba — ADOPT-WHEN-MEASURED (architecture constraint now, dependency later)
- **Reason:** JIT rescue for any per-tick logic vectorization can't express (contest loops in
  Phase 3). Phase 1 *designs for it* — physics kernels are pure functions over float64 arrays
  with no Python objects in signatures — but does **not** add the dependency, because profiling
  hasn't justified it (rule from design doc 05: profile first, Numba second).
- **License:** BSD-2. · **Performance:** 10–100× on scalar-loop code when needed.
  · **Maintenance:** healthy (Anaconda-backed); Python-version lag is why Python is pinned 3.12.
  · **Portfolio:** "deferred until profiling demanded it" is the senior answer.

### PyBullet — REJECT
- A rigid-body robotics engine. Provides none of the aerodynamics (drag, Magnus, drag crisis) —
  those would still be custom external forces, i.e. the hard part remains hand-built. No batch
  lockstep: 10k independent worlds stepped in Python is orders of magnitude slower than one
  vectorized array op. Determinism across platforms is not guaranteed. Its strengths
  (articulated bodies, joints, contacts among many objects) are unused: our contact model is a
  single sphere-on-plane impulse, ~40 lines with a closed-form solution.
- **License:** zlib (fine, irrelevant). · **Portfolio:** using a robotics engine to drop one
  ball reads as tool-grabbing, and the dependency would *obscure* the physics the project
  exists to demonstrate.

### Pymunk (Chipmunk2D) — REJECT
- 2D. Set-piece flight is irreducibly 3D (delivery height, jump reach, goal height, swerve in
  the horizontal plane simultaneously with drop). MIT license; moot.

### JAX — REJECT for v1 (revisit only for differentiable-sim research)
- `vmap`/`jit` would express batch elegantly, but: Windows support remains second-class for the
  primary dev machine; the functional constraints tax every contributor; and its killer feature
  (gradients through the simulator) is unused by the chosen optimization strategy (Bayesian/CMA-ES
  treat the sim as a black box, by design — ADR'd in the ML architecture). NumPy reaches the
  stated budget without it.
- **License:** Apache-2.0. · **Portfolio:** a JAX dependency used as "fast NumPy" signals
  fashion-following; a documented rejection signals judgment. Tier-3 differentiable-sim is the
  legitimate re-entry point.

### Monte Carlo tooling — ADOPT NumPy `Philox` + SciPy stats (no framework)
- Monte Carlo here is "run the simulator N times with independent RNG streams and aggregate."
  Frameworks (PyMC, Chaospy, SALib) solve *inference/sensitivity* problems we don't have.
  The real "buy" decisions: **counter-based Philox streams** (parallel-safe, replayable child
  streams per sim — already in NumPy) and **SciPy** for Wilson CIs and BCa bootstrap rather
  than hand-rolled statistics.

### Optimization tooling — ADOPT Optuna + cmaes (Phase 5, recorded now)
- **Optuna** (MIT): TPE over mixed categorical/continuous spaces, pruning, storage, plots —
  exactly the Phase-5 requirement; building this would be months. **cmaes** (MIT): clean CMA-ES
  for the continuous-subspace comparison study. Both deferred to Phase 5 so Phase 1 ships no
  unused dependencies.

### Supporting choice — pydantic for physics *configuration* (not state)
- Config models (`PhysicsConfig`) are cold-path, validated-once objects: pydantic v2 (MIT,
  already in the workspace) gives bounds validation, frozen immutability, and serializable
  scenario specs for free. Hot-path *state* stays as plain NumPy arrays / frozen dataclasses —
  validation at the boundary, raw arrays inside. (Considered: `pint` for units — rejected;
  per-op overhead in hot loops, SI-by-convention is enforced by the domain layer instead.)

## Decision

**Custom force/integrator/bounce kernels on NumPy** (the football IP), **SciPy as validation
oracle and statistics library**, **Numba-ready kernel architecture with the dependency
deferred**, **pydantic for configuration**, **Philox streams for Monte Carlo**, **Optuna/cmaes
earmarked for Phase 5**. PyBullet, Pymunk, and JAX rejected with rationale above.

## What stays custom (the IP boundary, per directive)

Aerodynamic coefficient models tuned to footballs; bounce/spin-transfer model; trajectory event
extraction (apex/bounce/goal-mouth crossing); Routine Spec & tactical compilation; Monte Carlo
outcome schemas; optimization workflows; everything analytics.

## Consequences

- A ~40-line RK4 and a closed-form impulse bounce are owned code — accepted: they are small,
  golden-tested, oracle-validated, and pedagogically central to the project.
- SciPy joins simulation-core's runtime dependencies (stats usage in Phase 3 makes it runtime,
  not dev-only).
- The Numba constraint shapes Phase-1 API design (array-in/array-out kernels, no closures over
  mutable state) — reviewed against that constraint even though Numba isn't installed.

## Addendum (2026-06-12, same phase): Numba adopted — the trigger fired

The "adopt-when-measured" condition was met during Phase 1 itself. Measured on the Phase-1
benchmark suite (4-core dev machine, single-threaded):

| Path | 10k corner flights | Notes |
|---|---|---|
| NumPy batch (lockstep `(n,9)`) | **6.76 s** (1,479/s) | One batched RK4 step = 17 ms — allocation/memory-traffic bound; a bandwidth back-of-envelope puts the NumPy floor near ~1 s even fully optimized |
| Fused Numba kernel | **0.98 s** (10,207/s) | Meets the < 1 s roadmap budget; `fastmath=False`, `cache=True` |

Decision: ``restart.physics._kernels.flight_batch`` (fused gravity+drag+Magnus+RK4+landing,
scalar loop per sim) is the **single production batch path** for the default force model;
custom force models route to the NumPy reference. The NumPy implementation is retained as
``_simulate_flights_numpy`` — the readable semantics oracle — and a kernel↔reference
equivalence test (≤ 1e-9 over 100 random flights) enforces that the two never drift, exactly
as ADR-002 d2 stipulated for the day Numba landed. Determinism contract unchanged: one
production path ⇒ identical inputs yield bit-identical outputs.

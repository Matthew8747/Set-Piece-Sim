# ADR-002 — Trajectory integration strategy

**Status:** Accepted · **Date:** 2026-06-12 · **Phase:** 1
**Related:** ADR-001; design doc 05 §2 (assumptions P-6)

## Context

The ball-flight ODE (gravity + speed-dependent drag + spin-dependent Magnus + spin decay) must
integrate (a) single trajectories with rich event extraction for replays/analysis and (b)
lockstep batches of 10⁴–10⁵ states for Monte Carlo. Design doc 05 prescribed fixed-step RK4 at
dt = 5 ms and "scalar reference implementation first, then a vectorized one, with equivalence
tests."

## Decisions

1. **Fixed-step RK4, dt = 5 ms, state vector y = [r, v, ω] ∈ R⁹.**
   Adaptive integrators (SciPy) are rejected for the hot path (per-trajectory step control
   breaks batch lockstep). RK4 at 5 ms gives ~1 mm-scale local accuracy on 25–35 m/s flights —
   verified by a convergence test (global error scales ~dt⁴) and the SciPy DOP853 oracle test
   (< 1 cm over a 40 m delivery, the P-6 acceptance bound). Spin decay is integrated inside the
   same state vector (dω/dt = −ω/τ) rather than applied as a post-step hack.

2. **One broadcast-polymorphic implementation instead of scalar + vectorized twins.**
   *Deviation from the approved design, in the project's favor:* all force and integrator
   kernels are written shape-generically over `(..., 3)`/`(..., 9)` arrays, so the *same code*
   serves the single-trajectory simulator `(9,)` and the batch engine `(n, 9)`. The planned
   scalar/vectorized equivalence test becomes vacuous (there is one implementation), and is
   replaced by strictly stronger checks: analytic closed-form comparisons, the SciPy oracle,
   convergence-order verification, and batch-vs-single consistency tests. The design doc's
   *intent* (a readable reference) is served by the scalar-shaped code path being the vectorized
   path. A hand-rolled scalar twin reappears only if/when Numba kernels (explicit loops) land —
   at which point the equivalence test does too.

3. **Events by sign-change detection + linear interpolation, not adaptive root-finding.**
   Apex (v_z sign flip), ground contact (z − r crossing), goal-plane and boundary crossings are
   detected between fixed steps and refined by linear interpolation within the step. At 5 ms
   steps the interpolation error is sub-millimeter — root-polishing (Brent) is unjustified
   machinery. Documented as assumption P-14.

4. **Batch engine integrates flight-to-first-ground-contact in lockstep with mask-freeze.**
   All sims step together; per-sim landing recorded at crossing via interpolation; finished sims
   are masked out of *recording* but stepping continues on the full array until all have landed
   or t_max — branchless vectorization beats fancy-indexed compaction at these sizes. Bounce
   chains and full event logs in batch mode arrive with the Monte Carlo layer (Phase 3), where
   the event-log schema is the contract.

## Consequences

- `restart.physics` exposes kernels as pure array functions (Numba-ready per ADR-001).
- dt is configuration (`IntegratorConfig`), but 5 ms is the validated default; changing it is an
  engine-version-bumping act once results are persisted (Phase 3 onward).
- The golden/convergence/oracle test trio becomes the permanent regression net for any future
  integrator change (e.g., a Numba rewrite must pass the identical suite).

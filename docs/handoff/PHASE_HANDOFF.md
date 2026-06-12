# Phase Handoff

> Rewritten at the end of every completed phase.

## Last completed phase: Phase 2 — Agents & tactical engine (`sim/0.2.0`)

### What shipped
`restart.players` (attribute column ABI, entities, demo squads) · `restart.agents`
(kinematics/interception/separation kernels) · `restart.tactics` (Routine Spec `rs/1.0`,
schemes incl. FK wall, compile→SoA SimProgram, content library) · `restart.engine`
(SetPieceEngine: delivery execution, pre-kick run development, Gumbel-max contests, GK save
model, typed match events with embedded xG features, deterministic replay tracks) ·
ADR-003/004 · G-1..G-13 registered. Details: [CHANGELOG](../../CHANGELOG.md) Phase-2 entry.

### Validation evidence
251 tests green (mypy strict, ruff, black clean). Phase-2 acceptance held: 10 routine×scheme
corners run start-to-terminal; kinematic envelope never violated (track-derived speeds);
bitwise determinism per seed; seeds vary outcomes; FK compiles & runs (PRD A-3 "configuration
not construction" confirmed); ShotEvent features sane; event streams time-ordered.

### Debugging history worth knowing (saves future sessions time)
1. Spin-sign convention was inverted (inswinger curled out of play) — fixed in
   `tactics/compile._spin_sign_and_rps` with derivation comment; verify against Magnus
   direction if touched again.
2. Corner kick position must sit INSIDE the goal-line plane (52.2, ±33.7) or every inswinger
   exits play immediately.
3. Fixed delivery elevation underflew 30 m targets — elevation now range-solved with carry
   factor (G-11).
4. Static zonal defenders beat arriving runners with a 60 ms contest window — widened to
   0.20 s [knob]; runners' pre-kick development needs ≥1.2 s lead (accel-limited agents move
   <1 m in 0.5 s).

### Open decisions carried forward
- Contest weights, GK save coefficients, keeper-claim bonus, carry factor: all uncalibrated
  `EngineConfig` knobs — the Phase-3 calibration surface.
- G-13 (plan-once interception) revisit only if face-validity fails.

## Current phase: Phase 3 — Monte Carlo, analytics, optimization interfaces, MVP

Scope per product-owner directive: batch runner (seeded streams, aggregation), outcome
metrics (goal/first-contact/header/shot/clearance/possession-recovery probabilities) with
Wilson + bootstrap CIs, simulation reports, optimization extension points (interfaces only —
no algorithms), AND the MVP vertical slice: REST endpoints (routines, simulate, batch) +
Scenario Workbench MVP (routine selector, sim trigger, results panel, event timeline, basic
pitch SVG). Simplified data acceptable; integration proof is the objective.

### Risks for this phase
1. Single-sim engine is ~30–80 ms ⇒ NumPy-loop batches of 10k ≈ 5–13 min. Acceptable for MVP
   (run 200–1000 sims synchronously); the fused Numba scenario kernel remains the documented
   Phase-3 performance deliverable (ADR-003 d8) and can follow the MVP.
2. API must enforce sim-count bounds (cost-bomb protection per security checklist).
3. Frontend MVP should consume typed shared-types mirrors of the new DTOs.

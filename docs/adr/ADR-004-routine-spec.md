# ADR-004 - Routine Spec `rs/1.0` and compile-to-SimProgram contract

**Status:** Accepted · **Date:** 2026-06-12 · **Phase:** 2
**Related:** ADR-003, design doc 05 §4, DB schema doc 03 (`routines.spec` JSONB)

## Context

One artifact must serve four masters: the UI scenario builder (Phase 6), the optimizer genome
(Phase 5), the replay metadata (Phase 6), and the execution input (now). Design doc 05 sketched
the JSON shape; this ADR fixes the v1 contract.

## Decisions

1. **The spec is a validated pydantic document** (`RoutineSpec`, `spec_version="rs/1.0"`):
   delivery (type, target point, speed, spin) + per-role assignments (start position, run legs
   with triggers and delays, intent). Defensive structure is *not* part of the routine - it
   lives in `DefensiveScheme` (zonal positions / marking counts / GK position / FK wall size),
   because the optimizer mutates routines against a *fixed* opponent scheme.

2. **Validation rejects, never repairs.** Off-pitch positions, duplicate roles, zero
   ball-attackers, kinematically absurd delays - all raise. The optimizer must learn real
   constraints (design doc 05 §4); silent fixes would corrupt the search space.

3. **Triggers are a small closed vocabulary** (`kick_approach` ≈ t−0.5 s, `kick` = t0,
   `ball_apex`), compiled to absolute times against the sampled flight. No free-form
   conditions in v1 - every trigger must be representable as a float in the compiled program.

4. **`compile_scenario(...) -> SimProgram` resolves everything ahead of the hot loop:**
   roles → player indices, attributes → an `(n, N_ATTR)` float64 matrix with a fixed column
   IntEnum, runs → padded waypoint tensors + trigger-time arrays, man-marking → greedy
   nearest-threat assignment (marker quality ordered by `marking` attribute), FK wall →
   positions on the 9.15 m arc. `SimProgram` is flat, read-only, float64/int64 - directly
   consumable by a future Numba kernel (ADR-003 d8). The hot loop contains **no dict lookups,
   no string comparisons, no pydantic objects.**

5. **Set-piece polymorphism by configuration.** `set_piece ∈ {corner, free_kick}` (v1):
   corners pin the kick position to the corner arc; free kicks take an arbitrary dead-ball
   position and add the wall via the scheme. Throw-ins are a Tier-2 extension of the same
   schema (delivery speed caps), per PRD assumption A-3 - the Phase-2 FK test is the
   feasibility evidence.

## Alternatives considered

| Alternative | Rejected because |
|---|---|
| Relational decomposition (runs/waypoints as rows) | The spec is a document mutated as a unit by the optimizer; decomposition buys nothing (DB doc 03 already settled JSONB) |
| Free-form trigger expressions | Un-compilable to arrays; unbounded validation surface; nothing in the corner playbook needs it |
| Marking resolved at runtime each tick | Per-tick assignment churn is kernel-hostile and unrealistic (markers don't re-auction marks mid-flight) |
| Defense inside the routine spec | Breaks the optimizer contract (search attacking space against fixed defense) |

## Consequences

- The optimizer's search space (Phase 5) = a typed subset of spec fields; bounds already
  enforced by validation.
- Spec JSON serializes losslessly (pydantic) into `routines.spec` JSONB per the DB schema.
- Schema evolution is explicit: breaking changes mint `rs/2.0` and a migration shim.

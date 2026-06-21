# ADR-009 — Scenario realism: wider attacker template, basic free kicks, structured defence

**Status:** Accepted · **Date:** 2026-06-21 · **Phase:** 8
**Related:** ADR-004 (Routine Spec / compile contract), ADR-006 (`restart_opt` over the pure
objective), design doc 05 (engine future work), design doc 09 (optimization methodology),
assumptions O-2 / O-3 / R9. **`ENGINE_VERSION` `sim/0.4.0` → `sim/0.5.0`** (first engine change since
Phase 4).

## Context

Review of the Phase 7 replays surfaced two realism gaps. The simulated corner placed only the
routine's runners + kicker as attackers — `compile_scenario` instantiates exactly the assignment
runners (`CornerGenome` default `n_runners=4`, so 5 attackers) — against a `DefensiveScheme` that
*always* accounts for 10 outfield + GK = 11. So screens showed ~5 vs 11 and too little routine
variance (every runner targeted the six-yard box). The engine and the hand-built routine library
already supported richer play (off-ball routines, a `direct_free_kick`, near-post zonal coverage);
the **genome** — the space the optimizer can actually search — was the narrow part.

Three forces shaped the decisions. The **pure-domain rule** keeps all changes in `restart.optimize`
and `restart.tactics` (no web/DB/ML/IO). The **O-2 registered assumption** excludes variable-arity
search, so attacker count must stay fixed within a study. The **throughput reality** (~3 sims/s, and
slower with more attackers; the 🔴 fused kernel still owed) caps how big the re-baselined study can
be.

## Decisions

1. **Wider corner template: 7 attackers with off-ball roles, fixed arity.** `ZONE_GRID` gains
   off-ball target zones (`top_of_box`, `left_half_space`, `right_half_space`, `deep_recycle`) so not
   every runner contests the six-yard box; the runner template grows to 7 slots (kicker + up to 6
   runners). `n_runners` stays **fixed per study** (honors O-2: no variable-arity search), with the
   canonical study raised to 6 runners (7 attackers). Slots beyond the box default to off-ball
   intents (`decoy` / `screen` / `second_ball`). CRN pairing and SHAP attribution are unaffected
   because the search space is fixed within a study.

2. **Basic free-kick genome, over existing engine scaffolding.** A `FreeKickGenome` reuses the runner
   template and builds a `FREE_KICK` routine; the kick origin (`fk_position`) is carried on the base
   `Scenario` (study config, not searched) and the wall is the defensive scheme's concern
   (`wall_size`) — both already compiled by `compile_scenario`. The corner and free-kick genomes share
   extracted template builders (`_template_params` / `_build_delivery` / `_build_assignments` /
   `_role_map`) so they cannot drift apart silently; the genome tests police the equivalence.
   **Offside lines and runners-from-off-the-ball timing are NOT modeled** — that stays the carried
   **O-3** fidelity cut (a later engine phase), stated here so the free-kick claim is not over-read.

3. **Structured defensive default.** A `near_post_man` `DefensiveScheme` (an explicit near-post
   anchor + a flat line + man-markers, summing to the =10 outfield invariant) joins the library
   beside the existing zonal/man/hybrid schemes. The canonical corner study keeps the
   near-post-covering `zonal_six_two` for continuity; `near_post_man` is available for studies that
   want explicit man-coverage of the near post. No change to the scheme model or the compile logic.

4. **Bump `ENGINE_VERSION` and re-baseline.** Placing more attackers changes a given routine's
   simulated context and therefore its results, so the engine build id bumps `sim/0.4.0` → `sim/0.5.0`
   (engine determinism is preserved — the same `Scenario` is still byte-identical). The committed
   canonical `study.json` is regenerated with the 7-attacker genome at the existing scoped budget
   (`--trials 24 --screen 40 --confirm 400 --k 3 --seed 0`); the old study reads `stale` against the
   new version until regenerated (the Phase 7 read-only surface already tolerates that).

## Consequences

- The optimizer can now express realistic overloads (box contesters + lurkers/recyclers) and basic
  wide free kicks, so "find the best routine" searches a space that looks like real set-piece play.
- More attackers = more compute per sim; study budgets stay **scoped** (ADR-006) until the 🔴 Numba
  kernel lands — this phase does not widen the budget.
- No frontend/API change: player tracks render dynamically (7 attackers just appear), the
  parallel-coordinates view gains axes automatically, and the OpenAPI/shared-types contract is
  unchanged (the `study.json` shape is stable — only its parameter count grows).

## Explicitly NOT in scope (deferred)

- **Evolutionary search (GA / CMA-ES) + family/branch lineage visualization** — a later optimizer
  phase, gated on the 🔴 fused Numba kernel for any real budget (doc 09 §11).
- **Offside lines, off-ball runner timing, multi-touch pass-then-shot** — carried **O-3**.
- **Engine `[knob]` calibration (🔴)** and the **fused Numba kernel (🔴)** — their own phases; the
  goal rate is still ~5% sim vs 2–3% real, so any "winner" is still read as a routine *class*.

# ADR-010 — Evolutionary routine search (CMA-ES + NSGA-II)

**Status:** Accepted · **Date:** 2026-06-21 · **Phase:** 9
**Related:** ADR-006 (`restart_opt` over the pure objective — this extends its sampler set), design
doc 06 §3.2 / doc 09 (optimization methodology), ADR-009 (the 7-attacker genome this evolves over),
assumptions O-1 (single-objective). **`ENGINE_VERSION` unchanged (`sim/0.5.0`)** — optimizer-only.

## Context

The product's headline is *set-piece routines that develop naturally by simulation*. v1 searched with
Optuna **TPE** plus the mandatory equal-budget **random** baseline — sample-efficient, but not
*evolutionary*: there is no population, no selection/crossover/mutation, no notion of a routine
*lineage*. The 7-attacker genome from Phase 8 (ADR-009) gives a 22-gene mixed search space with real
room to evolve. The optimizer was deliberately built sampler-agnostic — `make_sampler(name, seed)`
maps a string to an Optuna sampler and the whole screen→confirm→persist pipeline is independent of
which sampler ran — so adding genuine evolution is a sampler addition, not new infrastructure. The
design doc promised it ("optimization interfaces (Optuna/CMA-ES-ready)").

## Decisions

1. **Two evolutionary samplers behind the existing dispatch.** `make_sampler` gains:
   - **`nsga2`** — Optuna's `NSGAIISampler`, a **genetic algorithm**: it evolves the *full* mixed
     genome (delivery + zones + intents + timings) via tournament selection, crossover and mutation —
     including the categorical genes. This is the literal "routines develop naturally, generation by
     generation" mechanism and the headline.
   - **`cmaes`** — Optuna's `CmaEsSampler` (an **evolution strategy**), strongest on the continuous
     delivery/timing genes; it samples categoricals independently, so it is positioned as the
     *continuous complement*, not the full-genome evolver. Needs the optional `cmaes` dependency
     (added to the optimizer package); NSGA-II is built into Optuna.
   Everything downstream — the pure genome, the xG fitness, common-random-number seeding, the
   screen→confirm pipeline, persistence, and the Phase-7 parallel-coordinates view — is unchanged.

2. **Population sized to the budget.** Evolutionary samplers run a *population* per generation; a
   default population (e.g. Optuna's 50) at a 24-trial budget yields < 1 generation — no evolution.
   The population defaults to `max(4, n_trials // 3)` (~3 generations at the canonical budget), so
   real generational pressure occurs. Evolutionary screens run with **pruning off** (an ES/GA needs
   full evaluations to update its population; a mid-trial prune would corrupt a generation).

3. **The generation is recorded as first-class lineage.** Each trial carries its NSGA-II
   `generation` index (read from Optuna's `system_attrs`), persisted to `study.json`. This is what
   lets the trial cloud be read as an *evolutionary lineage* (the Phase-7 parallel-coordinates /
   convergence views can colour by generation — a small frontend follow-up).

4. **Canonical comparison + honest, equal-footing confirm.** The canonical study now runs **three**
   searches at equal budget — TPE, random, and NSGA-II evolution — and confirms the best-k routines
   found by **either** TPE or evolution under one CRN seed, recording **which sampler** produced the
   winner. The honesty bar is unchanged: any sampler (evolution included) must beat random at equal
   budget or it is theatre (doc 09 §5). CMA-ES is available via the library API but kept out of the
   canonical run to bound compute (documented).

5. **Single-objective now.** Evolution optimizes mean xG (assumption O-1); counterattack risk stays
   reported-not-optimized. NSGA-II is *natively* multi-objective, so an (xG, −counterattack-risk)
   **Pareto front** — handing a coach a frontier of aggressive↔safe routines — is the clean next
   step; it needs the objective to return both metrics and is deferred to its own phase.

## Consequences

- Evolution is real and demonstrable: the canonical `study.json` carries an `evolution` block with a
  per-trial generation lineage beside `tpe`/`random`, and the winner is the best across samplers.
- No engine change, no determinism change (each sampler is seeded → reproducible), no `ENGINE_VERSION`
  bump. The OpenAPI/shared-types contract is unaffected (the `study.json` gains an additive block + an
  optional `generation` field, which the Phase-7 read-only surface tolerates).
- The 🔴 Numba kernel (throughput) is **not** a blocker for evolution at the scoped budget — but it is
  what scales it (bigger populations / more generations). Evolution is therefore Phase 9; throughput
  becomes Phase 10 (a reorder of the roadmap, justified by evolution being the product's selling
  point and feasible at the current budget).

## Explicitly NOT in scope (deferred)
- **Multi-objective Pareto** (xG vs counterattack risk) — NSGA-II's native strength; needs the
  objective to emit both metrics + a Pareto UI (roadmap §4).
- **Lineage / generation visualization** in the frontend (colour the parallel-coords by generation,
  an "evolution" convergence series) — a Phase-7-surface follow-up.
- **Larger populations / more generations** — gated on the 🔴 Numba kernel (Phase 10, roadmap §1).

# Phase Handoff

> Rewritten at the end of every completed phase.

## Last completed phase: Phase 9 — Evolutionary routine search (`restart_opt`)

> Built on `feat/phase8-scenario-realism` (needs the 7-attacker genome). Phase 7 (optimization UI /
> 3D replay, PR #7) and Phase 8 (scenario realism, PR #8) are the parallel branches off `main`.
> `ENGINE_VERSION` unchanged (`sim/0.5.0`) — this is an optimizer-only phase.

### What shipped

- **Genuine evolutionary search behind the existing sampler dispatch.** `make_sampler`
  (`restart_opt/study.py`) gains `nsga2` (Optuna `NSGAIISampler` — a **genetic algorithm** that
  evolves the *full* mixed genome via selection/crossover/mutation, including the categorical
  zones/intents: the "routines develop naturally, generation by generation" headline) and `cmaes`
  (Optuna `CmaEsSampler` — an **evolution strategy** for the continuous delivery/timing genes). Both
  plug into the unchanged screen→confirm→persist pipeline; the only new dependency is `cmaes`
  (NSGA-II is built into Optuna). ([ADR-010](../adr/ADR-010-evolutionary-search.md), extends ADR-006.)
- **Population sized to the budget** (`default_population` = `max(4, n_trials // 3)`, ~3 generations
  at the canonical budget) so real generational pressure occurs; evolutionary screens run **pruning
  off** (an ES/GA needs full evaluations per generation).
- **Generation lineage as first-class data.** Each trial carries its NSGA-II `generation` index
  (read from Optuna `system_attrs`), persisted to `study.json` — so the trial cloud can be read as an
  evolutionary lineage (the Phase-7 parallel-coordinates / convergence can colour by generation, a
  frontend follow-up).
- **Canonical evolution comparison.** `run_canonical` now runs **three** searches at equal budget —
  TPE, the random baseline, and NSGA-II evolution — and confirms the best-k routines found by
  **either** TPE or evolution under one common-random-number seed (fair, equal-footing), recording
  **which sampler** produced the winner (`winner.sampler`). The committed `study.json` gains an
  `evolution` block + generation lineage beside `tpe`/`random`. The honesty bar is unchanged
  (evolution must beat random at equal budget or it is theatre).
- **Single-objective** (mean xG, assumption O-1). NSGA-II's native multi-objective (xG vs
  counterattack-risk Pareto) is the documented next step.
- **Docs:** ADR-010, the roadmap reorder (evolution = Phase 9; throughput = Phase 10) + a new UI &
  features section (lineage / "watch it evolve" view, sampler comparison, Pareto explorer).

### Validation evidence

All Python gates green (ruff, black, mypy --strict, pytest). Optimizer suite covers the new samplers:
toy-landscape (CMA-ES finds the peak; NSGA-II evolves generations over a *mixed* genome; determinism
per seed), engine-backed NSGA-II screen (generations recorded, reproducible), generation round-trip
through persistence, and the canonical smoke (three searches + winner-sampler + lineage). The
canonical study was re-baselined with the observable watchdog wrapper; the regenerated `study.json`
carries the `evolution` block (sampler `nsga2`, generations 0–2) beside `tpe`/`random`.

**Honest result (scoped budget — 24 trials, population 8, ~3 generations):** evolution's screen best
(≈0.050) **beat the random baseline** (≈0.043) — the honesty bar passes — but **TPE still won**
(≈0.067); the union-confirm correctly tagged the winner `sampler="tpe"`. This is expected and not a
strike against evolution: a GA needs *more generations / larger populations* to overtake model-based
TPE, and that is precisely what the 🔴 Numba throughput kernel (Phase 10) unlocks. The winner stays
flagged for bound-pinning (`target_x`/`target_y`) — the anti-exploit guard firing as designed — and
the carried 🔴 calibration still caps how literally any xG level reads.

### Debugging history worth knowing (saves future sessions time)

1. **`CmaEsSampler` needs the optional `cmaes` package** — Optuna raises `ModuleNotFoundError: No
   module named 'cmaes'` without it. Added to the optimizer package deps. (NSGA-II is built in.)
2. **NSGA-II's generation key is `NSGAIISampler:generation`** in Optuna 4.x (older docs say
   `nsga2:generation`). `_generation_of` checks both for version-robustness.
3. **Population must be sized to the budget.** Optuna's default population (50) at a 24-trial budget
   yields < 1 generation — no evolution. Size it to `n_trials` (`default_population`).
4. **Evolutionary samplers + pruning don't mix** — a mid-trial MedianPrune corrupts the generation
   step; `run_screen` forces pruning off for `cmaes`/`nsga2` regardless of the `prune` flag.

### Open decisions carried forward (NOT touched by Phase 9)

- **Multi-objective Pareto** (xG vs counterattack risk) — NSGA-II's native strength; needs the
  objective to emit both metrics (roadmap §4).
- **Lineage visualization** — colour the parallel-coords by generation, an "evolution" convergence
  series (roadmap §7); a Phase-7-surface follow-up.
- **Throughput (🔴, now Phase 10):** the fused Numba kernel — scales evolution (bigger populations /
  more generations). Evolution works at the scoped budget today; the kernel lifts it (roadmap §1).
- **Calibration (🔴):** fit the engine `[knob]`s to real base rates (roadmap §2).

## Next phase: Phase 10 — Throughput (fused Numba scenario kernel)

Port the engine semantics into a `@guvectorize`/`njit(parallel)` kernel over the flat `SimProgram`
SoA arrays; police drift against the reference engine with a `≤1e-9` equivalence test. Target
10⁴–10⁵ sims/s — which lets evolution run *real* populations over many generations and unlocks the
full reference budget (calibration, multi-objective). See ADR-003 d8 + roadmap §1.

### Risks for Phase 10
1. Physics drift between kernel and `forces.py` — contained by the equivalence test.
2. Determinism under parallelism — per-sim `SeedSequence` seeds are scenario-independent; assert
   byte-identity across batch sizes.
3. A behaviour change would bump `ENGINE_VERSION` and force another re-baseline — keep it a faithful
   port.

# Phase 9 — Evolutionary Routine Search — Design

**Status:** Approved · **Engine:** `sim/0.5.0` (unchanged — optimizer-only phase) ·
**Branch:** `feat/phase9-evolution` (off `feat/phase8-scenario-realism`; needs the 7-attacker genome)

## 1. Goal

Make the product's headline real: **set-piece routines that develop naturally by simulation.** Add
genuine evolutionary search to the optimizer — a genetic algorithm (NSGA-II) that evolves the *full*
mixed genome (delivery + zones + intents + timings) generation by generation, and CMA-ES (an
evolution strategy) for the continuous delivery/timing sub-genome — alongside the existing TPE and the
mandatory equal-budget random baseline. Persist a per-trial **generation index** so the trial cloud
can be read as a lineage.

## 2. Why this is small (the architecture was built for it)

The optimizer is sampler-agnostic. `make_sampler(name, seed)` (`restart_opt/study.py`) maps a string
to an Optuna sampler; everything downstream — the pure mixed-type genome (`SearchSpace` →
`Scenario`), the xG fitness (`RoutineObjective`), common-random-number seeding, the screen→confirm
pipeline, persistence, and the Phase-7 parallel-coordinates view — is independent of which sampler
ran. Optuna 4.9 ships `CmaEsSampler` and `NSGAIISampler`. The design doc promised this
("Optuna/CMA-ES-ready"). So evolution is a sampler addition + plumbing, not new infrastructure.

## 3. Decisions (from brainstorming)

- **Both algorithms.** NSGA-II (genetic — selection/crossover/mutation over the *full* genome,
  including the categorical zones/intents — the "routines develop naturally" headline) **and** CMA-ES
  (evolution strategy — strongest on the continuous delivery/timing genes).
- **Canonical evolution study.** Extend the canonical pipeline so the committed `study.json` carries
  an **evolutionary** screen outcome beside `tpe` and `random`, at equal budget (the honesty bar:
  evolution must beat random at equal budget or it is theatre). Persist a **generation index** per
  trial for the lineage view.
- **Single-objective now.** Evolve toward mean xG; counterattack risk stays reported-not-optimized
  (O-1). Multi-objective (NSGA-II's native (xG, −risk) Pareto front) is a clean follow-up phase.

## 4. Components

### 4.1 Samplers + generation tracking (`restart_opt/study.py`)
- `make_sampler` gains `"cmaes"` → `CmaEsSampler(seed=seed)` and `"nsga2"` →
  `NSGAIISampler(seed=seed, population_size=...)`. A small **population sized to the budget** so real
  generations occur (default `max(4, n_trials // 3)` ⇒ ~3 generations at 24 trials; a 50-default would
  be < 1 generation = no evolution). `make_sampler` takes an optional `population_size`.
- `Sampler` allowed set: `{"tpe", "random", "cmaes", "nsga2"}`; the validation error lists them.
- `TrialRecord` gains `generation: int | None`. `build_outcome` reads NSGA-II's
  `trial.system_attrs["nsga2:generation"]` (None for non-generational samplers).

### 4.2 Screen plumbing (`restart_opt/screen.py`)
- `run_screen` threads an optional `population_size` to `make_sampler`. Evolutionary screens run with
  **pruning off** (an ES/GA needs full evaluations to update its population; mid-trial pruning would
  corrupt the generation step) — the caller passes `prune=False` for `cmaes`/`nsga2`.

### 4.3 Persistence (`restart_opt/persist.py`)
- `outcome_to_dict` includes `generation` in each serialized trial (so the lineage is in `study.json`).

### 4.4 Canonical comparison (`restart_opt/canonical.py`)
- Add an **evolutionary screen** (`nsga2`, the full-genome GA — the headline) at the same trial/budget
  as TPE/random, persisted as `document["evolution"]` with its sampler name + generation indices.
- The **winner/confirm** pool becomes the **union** of the TPE and evolution top-k, confirmed under
  the same CRN seed — so the reported winner is the best across samplers, and the comparison is fair.
  (CMA-ES is available via the CLI but not added to the canonical run, to bound compute; documented.)

### 4.5 CLI (`restart_opt/cli.py`)
- The `canonical` command always includes the evolution screen now. A `--sampler {tpe,random,cmaes,
  nsga2}` option on a lighter `screen`/`evolve` path lets a user run any single sampler. (Keep it
  minimal — the canonical is the demo.)

## 5. Testing (TDD)
- `make_sampler` returns the right Optuna sampler for each name; unknown name raises listing the four.
- `run_study`/`run_screen` complete with `cmaes` and `nsga2` on the engine-free toy landscape and
  produce a valid `StudyOutcome` (trials, best, generation populated for nsga2).
- **Generation index**: an nsga2 outcome has trials with `generation` set (0,1,2…); tpe/random have
  `None`. Round-trips through `outcome_to_dict`.
- **Honesty**: on the toy landscape, evolution's best ≥ random's best at equal budget (sanity, not a
  hard SLA — guarded loosely to avoid flakiness).
- Determinism: same seed ⇒ same trials for each new sampler.

## 6. Re-baseline
- Re-run the canonical study (now TPE + random + evolution + union-confirm) via the observable
  watchdog wrapper at the committed budget. `study.json` gains the `evolution` block + generation
  indices; `engine_version` stays `sim/0.5.0` (no engine change). Update any test pinning the study's
  top-level keys.

## 7. Ripple & risks
- **Frontend (P7 branch):** the parallel-coordinates view already renders any trial cloud; coloring by
  `generation` (the lineage view) is a small P7 follow-up, not in this phase. The convergence plot
  could gain an "evolution" series likewise. No change on this branch.
- **Risk — population vs budget:** too-large a population at a small budget yields < 1 generation (no
  evolution). Mitigated by sizing population to `n_trials`.
- **Risk — CMA-ES on categoricals:** CMA-ES samples categoricals independently (with a warning); it is
  positioned as the *continuous* complement, NSGA-II as the full-genome GA. Documented.
- **Risk — compute:** the evolution screen adds ~one more screen phase to the canonical run; bounded +
  observable via the existing wrapper.

## 8. Milestones
- **M1** samplers + generation tracking in `study.py` (+ tests).
- **M2** `run_screen` population plumbing + `persist` generation (+ tests).
- **M3** canonical evolution comparison + union-confirm + CLI (+ tests).
- **M4** re-baseline canonical with evolution (observable wrapper); update pinned tests. Full gate.
- **M5** ADR-010 + roadmap reorder (evolution = Phase 9, throughput = Phase 10) + handoff + PR.

# ADR-006 - System B: the routine optimizer (Optuna over the pure objective)

**Status:** Accepted · **Date:** 2026-06-14 · **Phase:** 5
**Related:** design doc 06 (ML architecture §3), ADR-001 (Optuna/cmaes earmarked P5), ADR-003
(engine throughput, fused-kernel debt d8), ADR-004 (Routine Spec = the genome),
ENGINE_VERSION `sim/0.4.0` (unchanged)

## Context

Phase 5 makes the platform *discover* corner routines and *explain* them (System B). Three forces
shape the implementation: the **pure-domain rule** (`restart` imports no Optuna/ML/IO), the
**noise** in the objective (mean xG over expensive, stochastic simulations), and the **throughput
reality** (the reference engine runs ~3 sims/s, measured). The design itself is fixed in design
doc 06 §3; this ADR records the execution decisions.

## Decisions

1. **Two-layer split: pure core + driver package.** The search algorithms do not belong in the pure
   core, but the *genome, objective, statistics, and guards* do. So `restart.optimize` (pure) gains
   the genome (search space + genotype→Scenario builder), the mean-xG objective, the
   screen-then-confirm statistics, and the anti-exploit guards - all deterministic and IO-free. A
   new sibling package **`packages/optimizer` (`restart_opt`, CLI `restart-opt`)** holds Optuna TPE,
   the random baseline, the engine-backed screen, study persistence, MLflow logging, the
   LightGBM+SHAP surrogate, and the sensitivity analysis. It depends on the core, never the reverse.
   This mirrors the `etl`/`ml` package pattern and keeps Optuna/LightGBM/SHAP/MLflow + filesystem IO
   out of the core. (Confirms the doc-06 framing that `restart.optimize` is the optimizer's home -
   for its *pure* contracts; the IO/ML engine is a sibling, because the pure-domain rule forbids it
   in the core.)

2. **Objective = mean xG per sim; counterattack risk reported, not optimized.** xG anchors the
   optimizer to reality (System A trains on real data only - no circularity). Counterattack risk is
   a coarse outcome-read proxy; multi-objective optimization is documented future work (doc 06 §3.2).

3. **~13-dim corner genome over a zone grid, not raw coordinates.** A fixed runner template with
   per-runner target *zones* (categorical), timing, and intent, plus the delivery params + type.
   Zones keep dimensionality sane and sampled genomes football-plausible; the lead-attacker intent
   is pinned to ATTACK_BALL so feasibility holds by construction. Infeasible genomes raise; the
   driver records a pruned trial (the optimizer learns constraints, never crashes - ADR-004 d2).

4. **Screen-then-confirm with common random numbers.** Small-budget TPE screen with median pruning
   under a shared per-sim seed stream → top-k re-evaluated at a large budget under a shared confirm
   seed → a discovery must beat the library baseline with non-overlapping 95% CIs. The mandatory
   random-search baseline runs at equal budget (or the optimizer is theater).

5. **Anti-exploit guard + sensitivity analysis.** Bound-pinning and a face-validity mean-xG ceiling
   flag likely simulator exploits for review. A ±10% curated-attribute perturbation re-ranks the
   top-k: stable ⇒ routine-precise claims; flips ⇒ report routine *classes* (doc 04 §3, roadmap R9).

6. **Scoped budget; the fused Numba kernel is deferred.** At ~3 sims/s the full reference budget
   (500 screen / 10k confirm / top-5 + equal random baseline) is ~14 h and cannot run in CI. The
   fused scenario kernel (ADR-003 d8) that would lift this is a large engine port that would consume
   Phase 5 and risk its quality, so it is **not** built here. Budgets are scoped and configurable;
   the 500/10k figures remain the documented reference methodology; the kernel stays a
   carried-forward 🔴 tech-debt item (the real path to 10⁵-10⁶-sim studies).

## Consequences

- The core stays pure (no new heavy/IO deps); `restart_opt` carries optuna/lightgbm/shap/mlflow with
  mypy `ignore_missing_imports` overrides (the P4 pattern).
- **`ENGINE_VERSION` is unchanged (`sim/0.4.0`)** - the optimizer does not touch engine physics.
- Studies are deterministic, resumable JSON under `optimization_studies/` and logged to MLflow
  (SQLite); `restart-opt canonical --seed N` reproduces any shipped study number.
- Canonical studies are budget-limited until the kernel lands; the case-study writeup states the
  exact budget used and that demo squads stand in for mart-derived squads (Phase 6).

## Alternatives considered

- **Optuna driver inside the pure core** - rejected: adds Optuna (and the temptation of IO) to the
  core's dependency surface; the sibling-package split is cleaner and matches `etl`/`ml`.
- **Build the Numba kernel first, then run the full budget** - rejected for Phase 5: too large to
  land alongside the optimizer deliverables without risking the phase; scoped budgets + honest
  documentation is the senior-engineer call.
- **CMA-ES / GA comparison studies** - deferred (doc 06 §3.2 Tier-2): valuable narrative, not
  required for the acceptance gate; revisit when throughput allows.

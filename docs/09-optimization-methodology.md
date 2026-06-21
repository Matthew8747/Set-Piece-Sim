# Optimization Methodology — Restart Lab System B

**Version:** 1.0 · **Status:** Phase 5 · **Engine:** `sim/0.4.0` (optimizer does not change physics)

System B searches the space of corner routines for high-value plays against a given defensive
scheme and explains what it finds. This document is the methodology of record; the worked result
is [the England-vs-Argentina case study](case-studies/england-vs-argentina.md). The design is
fixed in [docs/06-ml-architecture.md §3](06-ml-architecture.md); this document records *how it is
implemented and why the numbers are trustworthy*.

## 1. The two-package split (pure core vs driver)

The simulation core (`restart`) is pure domain — no Optuna/ML/IO (the dependency rule). So System B
is split:

- **`restart.optimize`** (pure, in the core): the genome (search space + genotype→Scenario builder),
  the objective (params → mean xG), the screen-then-confirm statistics, and the anti-exploit guards.
  Deterministic and IO-free.
- **`restart_opt`** (the driver package): Optuna TPE + the random baseline, the engine-backed screen,
  study persistence, MLflow logging, the LightGBM+SHAP surrogate, the sensitivity analysis, and the
  CLI. It consumes the pure surface and never the reverse.

This keeps Optuna/LightGBM/SHAP/MLflow and all filesystem IO out of the core while still giving the
optimizer its designated home.

## 2. The objective

The objective is **mean xG per simulation**, scored by the real-data xG model already wired into the
engine (doc 06 §2.3). A simulation that produces no shot contributes 0. xG is the right objective
because it is anchored to real shot outcomes (System A is trained on real data only), so the
optimizer cannot drift toward the simulator's own biases the way a sim-trained target would.

**Counterattack risk is reported, not optimized.** It is a coarse proxy — the fraction of
simulations the defending side ends with the ball (clearance, keeper claim, defensive second ball,
or save). Multi-objective optimization (trading xG against counterattack exposure) is documented
future work (doc 06 §3.2); optimizing a single objective and *reporting* the risk is the honest v1.

## 3. The genome (search space)

A fixed corner template parameterized to ~13 dimensions (doc 06 §3.1):

- **Delivery:** target x, target y, speed, spin (continuous) + delivery type (categorical:
  inswinger / outswinger / driven / floated; SHORT excluded — different routine semantics).
- **Per runner (4 slots):** target *zone* (categorical over a fixed grid of box zones), run-timing
  delay (continuous), and intent (categorical). Slot 0's intent is pinned to ATTACK_BALL so every
  sampled genome satisfies the CORNER feasibility rule and no screen budget is wasted on infeasible
  trials.

A **zone grid** (not raw coordinates) is deliberate: it keeps the dimensionality sane and every
sampled genome football-plausible, rather than letting the optimizer place runners at arbitrary
points it can exploit. Infeasible combinations (should the lead-attacker pin be disabled) are
rejected by Routine Spec validation — the builder raises, the driver records a pruned trial, the
optimizer learns the real constraint instead of crashing.

> **Phase 8 (`sim/0.5.0`) widened this template** ([ADR-009](adr/ADR-009-scenario-realism.md)). The
> corner genome now fields up to **7 attackers** (kicker + 6 runners) and the zone grid gains
> **off-ball zones** (top-of-box, half-spaces, deep recycle) so not every runner contests the
> six-yard box — the canonical study runs 6 runners (a 22-dim genome). Arity remains **fixed per
> study** (no variable-arity search — assumption O-2), which keeps the search space constant so the
> common-random-number pairing (§4) and the SHAP attribution (§7) stay valid. A parallel
> `FreeKickGenome` reuses the same template for basic free kicks (offside / off-ball runner timing
> stay out — carried O-3); `fk_position` is study configuration, not a search dimension.

## 4. Screen-then-confirm with common random numbers

Cheap noisy evaluations, expensive confirmations (the headline methodological feature, doc 06 §3.2):

1. **Screen.** TPE proposes genomes; each is evaluated at a small budget (`n_screen` sims) under
   **common random numbers** — every trial sees the identical per-sim seed stream
   (`SeedSequence(seed)`), so differences between genomes are signal, not seed luck. Sims are run in
   chunks with the running mean xG reported to Optuna's **MedianPruner**, which abandons clearly poor
   genomes early.
2. **Confirm.** The screen's top-k genomes are re-evaluated at a large budget (`n_confirm` sims),
   again under a common confirm seed. The objective is a mean, so its uncertainty is a large-sample
   CI on the mean (not a Wilson proportion interval).
3. **Decision.** A discovery must beat the **library baseline routine** with **non-overlapping 95%
   CIs** (the candidate's CI lower bound above the baseline's CI upper bound). This is the honest bar.

## 5. The mandatory random-search baseline

Every optimizer must beat random search at equal budget or it is theater (doc 06 §3.2). The driver
runs a seeded `RandomSampler` study at the same trial count and per-trial budget as the TPE study.
On a smooth low-dimensional landscape random search is a strong baseline; TPE's sample-efficiency
advantage shows on the noisy, mixed-type, ~13-dim space here — and if it does not, the baseline
catches that honestly.

## 6. Anti-exploit guard

Optimizers find simulator bugs before they find football insights (doc 06 §3.2). Two cheap rules
feed a face-validity review of the top-k:

- **Bound-pinning:** any continuous/integer parameter sitting within ε of a search bound is flagged
  (the optimizer is riding a wall, often a model edge).
- **Face-validity ceiling:** a mean xG above a plausibility ceiling (real corner mean xG is far
  lower) is flagged as a likely exploit, not an insight.

Flagged discoveries are reviewed before any claim is made.

## 7. Surrogate & explainability

After a study accumulates trials, a **LightGBM** regressor is fit on (genome params → mean xG) and
**SHAP** attributes importance per feature. The top contributors are rendered as plain-language
"insights" ("delivery_type=inswinger is the strongest setting for mean xG …") — the differentiating
coach-facing panel. The surrogate explains the trial cloud; it never replaces the simulator.

## 8. Attribute sensitivity analysis

Curated player attributes are priors, not measurements (ADR-005, doc 04 §3). The harness perturbs
the curated attributes ±10% and re-ranks the top-k routines. If the best routine stays best under
every perturbation, the discovery is **routine-precise**; if the ranking flips, the writeup reports
routine **classes** ("near-post inswingers beat this zonal line"), not player-precise prescriptions
(roadmap R9).

## 9. Throughput reality & honesty (the budget decision)

The reference engine runs at **~3 simulations/second** (measured, with the xG model wired). The full
reference budget — 500-sim screens, 10k-sim confirmations, top-5 — would take **~14 hours** of
wall-clock for one study and cannot run in CI.

**Decision (ADR-006):** the fused Numba scenario kernel (ADR-003 d8) that would lift this is **not**
built in Phase 5 — it is a large engine port that would consume the phase and risk its quality. The
budgets are **scoped and configurable** instead, and the limitation is documented honestly:

- The committed canonical study uses a reduced budget (see its config block) the reference engine
  finishes offline.
- The 500/10k figures remain the documented *reference methodology*; pass larger `--screen` /
  `--confirm` once the kernel lands to reproduce them.
- The kernel remains a carried-forward 🔴 tech-debt item (it is the real path to 10⁵–10⁶-sim studies).

## 10. Reproducibility

Studies are deterministic (seeded TPE/random samplers; CRN seeds for screen and confirm) and
resumable/auditable as JSON under `optimization_studies/<name>/`. Every study is logged to MLflow
(local SQLite backend) with params, metrics, engine/optimizer versions, and git SHA. One command
rebuilds any shipped study number:

```
restart-opt canonical --seed 0 --trials 24 --screen 40 --confirm 400 --k 3 --sens 60
```

## 11. Out of scope (documented future work)

- Fused Numba scenario kernel (lifts the budget ceiling).
- CMA-ES and GA comparison studies (doc 06 §3.2 Tier-2).
- Multi-objective optimization (xG vs counterattack risk).
- Squad selection from the player marts (Phase 6; the canonical study uses demo squads).

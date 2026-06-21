# Restart Lab — Forward-Looking Enhancement Roadmap

**Audience:** engineering review / technical interview. **Status:** living document.
**Engine:** `sim/0.5.0` · **Optimizer:** `restart_opt` (Optuna TPE + random baseline).

This is the "what next, and why" companion to the shipped system. It is written to answer the
interview question *"you built v1 — where would you take it, and what are the trade-offs?"* Each item
states the **problem**, the **proposed approach**, **why it matters**, and a rough **effort/risk**.
Items already tracked as 🔴/🟡 in [`TECHNICAL_DEBT.md`](handoff/TECHNICAL_DEBT.md) are cross-referenced;
this doc adds the *technical depth and alternatives* an engineer would weigh.

The system is two coupled artifacts: a **deterministic physics + agent simulator** (`restart`) and a
**black-box optimizer over routines** (`restart.optimize` + `restart_opt`). The roadmap is organized
by where the leverage is: throughput, fidelity/calibration, the search itself, the objective, the ML,
and the platform.

---

## 1. Throughput — the keystone dependency (🔴)

**Problem.** The reference engine runs at **~3 sims/s** (single trajectory ~0.4 s; the 7-attacker
template is ~2.5× slower again). Every downstream ambition — bigger studies, evolutionary search,
multi-objective Pareto fronts, robust optimization — is gated on this. The current studies run at a
deliberately *scoped* budget (24 trials × 40-screen / 400-confirm) and are honest about it (ADR-006).

**Approach (in priority order).**
1. **Fused Numba scenario kernel (ADR-003 d8).** The hot path is already compiled to flat, read-only
   SoA arrays (`SimProgram`) precisely so a `@guvectorize`/`njit(parallel=True)` kernel can run a whole
   batch of sims with no Python in the loop. Port the RK4 flight + contest resolution; police drift
   against the reference engine with an equivalence test (`≤1e-9`, the same discipline already used for
   the JIT physics formulas). Target **10⁴–10⁵ sims/s**.
2. **GPU batch (JAX / CuPy).** Express the integrator and the per-sim agent updates as vectorized array
   ops; `vmap` over the sim dimension. Determinism via per-sim `SeedSequence`-derived keys (already the
   contract). Target **10⁶ sims** for a full 500/10k reference study in minutes.
3. **Distributed studies.** Optuna already supports an RDB storage backend; point it at Postgres (the
   adapter exists) and fan trials across workers (Arq is wired; Ray Tune is the heavier alternative).
   CRN is preserved because per-sim seeds are scenario-independent.

**Why it matters.** This is the single change that converts "a credible scoped demo" into "a research
instrument." It is also the cleanest systems-engineering story: the SoA compile boundary was designed
up front *for* this port.

**Effort/risk:** high effort, medium risk (equivalence test contains the risk).

---

## 2. Engine calibration — making the numbers trustworthy (🔴)

**Problem.** The xG *mapping* is calibrated (logistic slope ≈ 1.00 on real shots), but the simulated
*shot-context distribution* is not yet validated: the sim produces a goal rate ~5% vs 2–3% real. The
upstream `[knob]`s (drag-crisis, Magnus, restitution, roll friction, contest/GK models) are physically
plausible priors, not fitted parameters.

**Approach.**
- **Simulation-Based Inference (SBI).** Treat the engine as a stochastic simulator with parameters θ
  (the knobs) and fit θ to the real base rates in `mart_calibration_targets`. Options, increasing
  sophistication: (a) **Approximate Bayesian Computation** (reject/▷SMC on summary stats — goal rate,
  shot rate, first-contact rate, header share); (b) **Neural Posterior Estimation** (e.g. `sbi`'s SNPE)
  to learn p(θ | observed summaries) — gives a *posterior over knobs*, i.e. honest uncertainty on the
  calibration itself.
- **Held-out validation.** Fit on one tournament, validate base rates + Population Stability Index
  (PSI) per feature on the other (the G-15 off-manifold check, already planned).
- **Hierarchical priors.** Player-attribute priors (R9) are curated; a partial-pooling model would
  shrink noisy per-player estimates toward position-group means.

**Why it matters.** This is the difference between "the optimizer found a number" and "the number maps
to reality." It is the most *quant-flavored* item: the engine becomes a calibrated generative model,
and the calibration carries its own uncertainty.

**Effort/risk:** high effort, medium-high risk (identifiability — multiple knob settings may match the
same summaries; the posterior makes that explicit rather than hiding it).

---

## 3. The search — beyond TPE (🟡)

**Problem.** v1 uses Optuna **TPE** with a mandatory **equal-budget random baseline** (the honesty
bar). On a smooth, low-dim landscape random search is strong; TPE's edge shows on the noisy mixed-type
~13–22-dim space. But the search itself is single-fidelity-ish and single-strategy.

**Approach.**
- **Formal multi-fidelity.** The screen-then-confirm pipeline is a hand-rolled two-rung ladder.
  Replace with **ASHA / Hyperband / BOHB** — principled successive halving that allocates budget to
  promising genomes adaptively (the MedianPruner is a weak version of this). Big sample-efficiency win
  given the throughput constraint.
- **Evolutionary search (the requested "evolve through branches").** **CMA-ES** for the continuous
  sub-space (delivery + timings); **GA / NSGA-II** for the mixed categorical/continuous genome.
  Surface the **lineage tree** (parent→child genomes, fitness by generation) as a first-class
  visualization — the "family of sims, evolve the winners" idea. Gate on §1 throughput.
- **Better Bayesian optimization.** Move from TPE to a **GP / BoTorch** surrogate with a mixed-type
  kernel; batch acquisition (qEI / qKG) to exploit parallel workers; warm-start from the library
  routines (priors that already encode football knowledge).
- **Quasi-Monte Carlo screens.** Replace the i.i.d. screen seeds with **Sobol** sequences for lower
  integration variance per trial.
- **Conditional / hierarchical search space.** Today arity is fixed per study (O-2). Optuna's
  conditional parameters would let `n_runners` *itself* be searched without the combinatorial blow-up,
  with per-arity sub-spaces — a principled relaxation of the O-2 simplification.

**Why it matters.** This is the core "did you just call a library, or do you understand search?"
question. The roadmap shows the ladder: random → TPE → multi-fidelity → BO → evolutionary/MO, each
justified by a property of *this* landscape (noisy, mixed-type, expensive, multi-modal).

**Effort/risk:** medium effort per strategy; low risk (each is benchmarked against the random baseline
— if it doesn't beat random at equal budget, it is theatre and is dropped).

---

## 4. The objective — reward reshaping (🟡)

**Problem.** v1 optimizes **mean xG per sim** and *reports* counterattack risk without optimizing it
(O-1). Mean xG is anchored to real outcomes (the xG model trains on real data only) — a deliberate
anti-drift choice — but it is risk-neutral and single-objective.

**Approach.**
- **Risk-adjusted objectives.** (a) **Mean − λ·risk** (a tunable risk penalty); (b) **CVaR / quantile
  objective** — optimize the *worst-decile* outcome for tail-robust routines (you don't want a routine
  with high mean xG that also concedes breakaways); (c) a **Sharpe-like** xG/σ for consistency.
- **Multi-objective (Pareto).** **NSGA-II** or Bayesian MO (**qEHVI** — expected hypervolume
  improvement) over (xG, −counterattack-risk). Hand the analyst a *Pareto front* of routines, not one
  winner — far more useful to a coach weighing aggression vs safety.
- **Distributionally robust optimization.** Today a study optimizes against **one** fixed defensive
  scheme. Optimize against a **distribution / worst-case** over schemes (`near_post_man`, zonal, man,
  hybrid) — a minimax/DRO objective that finds routines robust to *how the opponent sets up*, which is
  what a coach actually wants pre-match.
- **Variance reduction.** Beyond CRN: **antithetic variates**, and using the **xG model as a control
  variate** (its analytic expectation reduces estimator variance), so confirmations need fewer sims.

**Why it matters.** Reward design is where domain insight meets optimization. CVaR/DRO are exactly the
vocabulary a quant interviewer wants to hear, and they map cleanly onto a real coaching trade-off.

**Effort/risk:** medium effort; low risk (additive to the existing objective seam).

---

## 5. ML — xG, surrogate, and explainability (🟡)

- **Calibrated intervals.** Add **conformal prediction** around xG so every shot carries a
  distribution-free coverage guarantee, not just a point + Platt scaling.
- **Monotonic constraints** on the GBM (closer/cleaner → higher xG) for face-validity and robustness.
- **Off-manifold gate (G-15).** A density model (e.g. Mahalanobis distance in feature space, or a
  normalizing flow) that flags simulated shot contexts lying off the real-shot manifold — so the
  optimizer cannot win by exploiting an extrapolation region of the xG model.
- **Close the surrogate loop.** The LightGBM+SHAP surrogate currently *explains* the trial cloud after
  the fact. Promote it to an **in-the-loop Bayesian surrogate** that drives the acquisition function —
  turning "insights" into search guidance.

---

## 6. Fidelity / agents (O-3, 🟡)

- **Multi-touch resolution.** A post-first-contact pass/lay-off step (cross → cut-back → tap-in is a
  real high-xG pattern). Pass success = skill/pressure model; the second contact's shot becomes the
  scored context.
- **Sequential decision lookahead.** A depth-limited **expectimax** over the post-contact phase:
  E[xG | shoot now] vs E[pass]·E[xG | next contact], pass-failure-weighted. Chess-engine-style shallow
  search, the natural follow-on to multi-touch.
- **Defender anticipation (partial observability).** Defenders react to ball + marks today; add a noisy
  prior over attacker intent so they anticipate back-post / cut-back threats *without* seeing the exact
  routine — closing an obvious exploit where the optimizer beats omniscient-but-static defenders.
- **Free kicks — full fidelity.** v1 ships a *basic* FK genome over existing scaffolding; the valuable
  part — **offside lines** and **runners timed from off the ball** — is the O-3 extension that makes FK
  routines genuinely distinct from corners.

---

## 7. Platform / product

- **Team-intelligence surface (`/teams`)** — squad aerial/pace profiles + an attacker×defender mismatch
  matrix (deferred from Phase 7.x).
- **Exportable report** — print-CSS A4 / PDF: the artifact an analyst hands a head coach.
- **CI for data-dependent + E2E suites** — wire the committed marts into CI so the Playwright journey
  and the mart-backed pytest run on every PR (currently local-only, gated on marts provisioning).
- **Richer data** — StatsBomb open is the license-clean base; player-tracking data (e.g. SkillCorner)
  would let run timings/speeds be *calibrated* rather than prior-driven.

---

## Suggested sequencing (dependency-aware)

```
Phase 9  Throughput: Numba scenario kernel        (unblocks everything below)
Phase 10 Calibration: SBI fit of the engine knobs (makes the numbers real)
Phase 11 Search+objective: ASHA + CMA-ES/NSGA-II + CVaR/DRO + lineage viz
Phase 12 Fidelity: multi-touch + lookahead + defender anticipation + full FK
Phase 13 Platform: /teams, report export, CI for data suites
```

The ordering is deliberate: **throughput first** (it is the multiplier on every search/calibration
experiment), **calibration second** (so the bigger searches optimize a trustworthy target), then the
richer search/objective/fidelity work that the first two unlock.

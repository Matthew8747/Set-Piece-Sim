# Machine Learning Architecture - Restart Lab

**Version:** 0.1 · **Status:** Design review draft

---

## 1. Framing: two ML systems, not one

The brief lists logistic regression, GBMs, Bayesian optimization, GAs, and RL as if they compete
for one job. They don't. There are **two distinct problems with different correct tools**:

| | System A: Outcome models (xG) | System B: Routine optimizer |
|---|---|---|
| Problem type | Supervised classification | Black-box optimization (search) |
| Data | Real historical shots (StatsBomb marts) | Simulator evaluations (expensive, noisy) |
| Output | Calibrated P(goal) for a shot context | High-value Routine Specs |
| Key risk | Miscalibration, leakage | Wasting sim budget; exploiting sim quirks |

Keeping them separate also kills a circularity trap: if xG were trained on the simulator's own
outcomes, the optimizer would optimize toward the simulator's biases with no reality anchor.
**System A is trained on real data only and is the simulator's ground-truth umbilical.**

```
real shots ──▶ [System A: xG models] ──┐ scores simulated shot contexts
                                       ▼
routine params ──▶ simulator ──▶ shot contexts ──▶ mean xG  ──▶ [System B: optimizer] ─┐
        ▲                                                                              │
        └──────────────────────── proposes next routine ──────────────────────────────┘
```

## 2. System A - Expected-goals layer

### 2.1 Models

Four contexts, two deployed models **(reversible)**:

- **`xg-header`**: headers and other non-foot first contacts.
- **`xg-foot`**: volleys, first-time shots, rebounds/second-ball strikes (with
  `set_piece_phase` and `is_rebound` features rather than separate models - set-piece foot-shot
  samples are too small to slice four ways; ~thousands, not tens of thousands, of open-data
  set-piece shots. Sliced models revisited only if learning curves say data permits).

Features (from freeze frames where available): distance, angle, body part, phase
(direct/first-contact/second-ball), defenders-in-cone count, nearest-defender distance, GK
position/depth, delivery speed proxy, under-pressure flag.

### 2.2 Method comparison (a deliverable, not a footnote)

| Candidate | Role | Expectation |
|---|---|---|
| Logistic regression (+ splines on distance/angle) | **Mandatory baseline** | Strong - xG is famously near-linear in the right basis; if GBMs can't beat it honestly, ship the baseline (that finding is itself portfolio-credible) |
| XGBoost / LightGBM | Primary candidates | Win if interactions (traffic × angle × phase) carry signal |
| CatBoost | Included in CV sweep only | Few high-cardinality categoricals here ⇒ unlikely to differentiate |
| Random forest | Included in sweep only | Dominated by boosting on tabular, kept as honest comparison |

Protocol: **grouped CV by match** (leakage guard - shots from one match never straddle folds),
metrics = log-loss, Brier, AUC, **calibration slope/intercept + reliability curves** (the metric
that matters for a model whose output feeds expectations), isotonic/Platt post-calibration
compared. Class imbalance (~10% conversion) handled by calibration-aware evaluation, not
naive resampling.

### 2.3 Integration with the simulator

The simulator emits *shot contexts* (geometry + traffic at strike). System A scores them.
Reported `mean_xG` = average scored xG per simulation; `P(goal)` = Bernoulli sampling from
scored xG (so goal events in replays are consistent with xG). Documented limitation: real-data
xG conditions on real-shot selection bias; simulated shot contexts can sit slightly off-manifold.
Mitigation: domain-overlap check (simulated feature distributions vs training distributions,
population-stability index per feature, reported in the model card).

### 2.4 Governance

Model cards (template per Google model-card schema: data, license, metrics, calibration plots,
intended use, limitations) stored in `ml_models.model_card`, rendered in the UI. MLflow tracks
every training run; `training_data_hash` chains model → mart snapshot.

## 3. System B - Routine optimizer

### 3.1 Search space

Parameterized subset of the Routine Spec, mixed-type, ~10-20 dims typical:
delivery type (categorical) × target point (2 cont.) × speed/spin (2 cont.) × per-runner start
zones and target zones (categorical-on-grid; keeps dimensionality sane vs raw coordinates) ×
run timing offsets (cont.) × role counts (int: how many attack vs screen vs edge).
Infeasible combos rejected by spec validation (optimizer sees a failure status, not a crash).

### 3.2 Method comparison & recommendation

| Method | Verdict | Rationale |
|---|---|---|
| Random search | **Mandatory baseline** | Every optimizer must beat it at equal budget or it's theater |
| **Bayesian optimization (Optuna TPE)** | **Recommended primary** | Sample-efficient on expensive noisy objectives; handles mixed categorical/continuous natively; pruning support; excellent built-in visualizations |
| Gaussian-process BO (BoTorch) | Rejected for v1 | GP machinery on mixed spaces = high complexity for marginal gain at this dimensionality |
| **CMA-ES (`cmaes` lib)** | **Comparison study (Tier-2)** | Strong on continuous sub-space (delivery parameters); natural head-to-head experiment for the case study |
| Genetic algorithm (DEAP) | Comparison study, time-permitting | Crossover over routine "genes" is narratively appealing; typically less sample-efficient; honest test |
| Evolutionary strategies (OpenAI-style) | Rejected | Gradient-estimator flavor suited to high-dim continuous policies, wrong shape here |
| Reinforcement learning | **Rejected for v1, scoped Tier-3** | This is a *one-shot design* problem (pick a routine), not a sequential policy problem - RL's machinery (credit assignment over time) is mostly dead weight; sample hunger × noisy sparse rewards × solo timeline = schedule killer. The honest framing where RL *would* fit: adaptive in-play agent behavior (Tier-3 research extension). Documenting this judgment is the portfolio value |

**Noise handling (the technically interesting part):** objective = mean xG over n sims/trial.
Budget allocation: 500-sim screens via TPE with median pruning → top-k re-evaluated at 10k sims
with common random numbers → winners must beat the baseline routine with non-overlapping 95% CIs.
This screen-then-confirm design (cheap noisy evaluations, expensive confirmations) is the
headline methodological feature.

**Anti-exploit guard:** optimizer discoveries that hinge on physics-edge behavior (e.g. deliveries
at validation boundaries) are flagged by rule (parameters within ε of bounds) and reviewed in V4
face-validity passes - optimizers find simulator bugs before they find football insights.

### 3.3 Surrogate & explainability

After studies accumulate trials: fit LightGBM on (routine params → mean xG) across all trials;
SHAP on the surrogate answers *"what makes a good corner against this defense?"* (e.g. "against
this zonal line, delivery 2 m beyond far-post zone + late near-post decoy = +0.04 xG"). Rendered
as a plain-language "insights" panel - the single most differentiating UI feature for the
coach persona.

## 4. Experiment infrastructure

- MLflow local backend; every System-A training run and System-B study logged with params,
  metrics, artifacts, git SHA, engine version.
- Deterministic seeds end-to-end; `make reproduce-xg` and `make reproduce-study STUDY=...`
  rebuild any shipped number.
- Tests: training pipeline smoke tests on a fixture mart; calibration-metric regression gates;
  optimizer integration test on a known toy landscape (recovers planted optimum).

## 5. Decision summary (what the brief asked us to weigh)

| Criterion | Chosen design |
|---|---|
| Performance | GBM-vs-baseline decided by held-out calibration, not leaderboard AUC; optimizer must beat random search at equal budget |
| Explainability | Splined-logistic interpretability standard; SHAP for GBMs + surrogate; model cards; assumption registry |
| Dev complexity | Optuna + sklearn + LightGBM = boring, reliable tools; complexity spent on the *evaluation protocol*, which is where the rigor shows |
| Portfolio value | The method *comparisons* (LR vs GBM; TPE vs CMA-ES vs GA vs random) and the noise-aware budget design are the interview material; a single unexamined XGBoost would be the weakest possible version of this project |

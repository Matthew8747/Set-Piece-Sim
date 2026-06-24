# Phase 5 - Optimization Engine (System B) - Design Spec

**Date:** 2026-06-14 · **Branch:** `feat/phase5-optimizer` · **Status:** Approved for planning

This spec implements Phase 5 of the roadmap (docs/08-roadmap.md) and System B of the ML
architecture (docs/06-ml-architecture.md §3). The design in those documents is **locked**; this
spec records only the *execution* decisions and the concrete interfaces/files to be built. It does
not re-litigate the locked design.

---

## 1. Goal & acceptance criteria

The platform **discovers** high-value corner routines against a given defensive scheme and
**explains** them.

Acceptance (from roadmap Phase 5):

1. TPE beats random search at equal budget (significant difference in best-found *confirmed*
   objective).
2. The top routine beats the library baseline with **non-overlapping 95% CIs** on the objective.
3. The SHAP insights panel data renders ≥ 3 plain-language findings a coach could act on.
4. The attribute-sensitivity conclusion is recorded (routine-precise vs routine-class).
5. All quality gates green (`scripts/verify.ps1`): ruff, black, mypy --strict, pytest, next build,
   eslint, tsc, vitest, prettier.

---

## 2. Locked decisions (from brainstorm)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Throughput | **Scoped configurable budget + optional process-pool parallelism.** The 500-screen / 10k-confirm budget is documented as the *reference methodology*; the committed canonical study runs at a reduced, honest budget the reference engine (~3 sims/s, measured) finishes offline. The fused Numba scenario kernel is **not** built this phase - it remains carried-forward 🔴 tech-debt; budgets are scoped around its absence and the limitation is documented. |
| D2 | Search space | **Medium genome, ~10-15 dims**: delivery (4 continuous) + delivery type (categorical) + per-runner target-zone (grid categorical) + per-runner run-timing offset (continuous) + per-runner intent (categorical), over a fixed corner template. |
| D3 | Placement | **New sibling package `packages/optimizer` (`restart_opt`, CLI `restart-opt`)** holds Optuna/LightGBM/SHAP/MLflow + persistence (all IO/ML). Pure pieces stay in `restart.optimize`. Mirrors the `etl`/`ml` package pattern. |
| D4 | Build workflow | **Inline** (no sub-agent dispatch) - optimizer code is determinism-sensitive and tightly coupled. |
| D5 | Engine version | Physics behavior **unchanged** → **no `ENGINE_VERSION` bump** (stays `sim/0.4.0`). New package ships `0.1.0`; repo milestone = Phase 5. |
| D6 | Scope cuts (YAGNI) | CMA-ES and GA comparison studies (doc 06 §3.2 Tier-2) **deferred** to future work, documented. Multi-objective optimization **deferred**; counterattack risk is **reported, not optimized**. |

### Throughput math (measured, ~3 sims/s with xG wired)

- 1 sim ≈ 0.33 s · 500-sim screen ≈ 2.75 min/trial · 10k-sim confirm ≈ 55 min/candidate.
- Full reference budget (TPE + equal random baseline, top-5 confirm @10k) ≈ **~14 h** wall-clock,
  and cannot run in CI.
- **Committed canonical study budget** (default, configurable): ~40 trials × 250-sim screen, top-3
  confirmed @ 3,000 sims, equal-budget random baseline. ≈ (40·250 + 3·3000)·2 ≈ 38k sims ≈
  **~3.5 h** offline; optional process-pool parallelism cuts this ~N_cores×.
- **Tests** use toy/tiny budgets (≤ ~30 sims, or an engine-free injected objective).

---

## 3. Architecture

```
real shots ─▶ [System A xG bundle (committed models/xg-v1.json)] ─┐ scores sim shot contexts
                                                                  ▼
genome ─▶ to_scenario ─▶ compile ─▶ MonteCarloRunner(xg engine) ─▶ mean_xg ─▶ [System B] ─┐
   ▲                                                                                      │
   └──────────────── Optuna TPE / random proposes next genome ────────────────────────────┘
```

- **Pure core** (`restart.optimize`, simulation-core): genome definition + `to_scenario`,
  objective (params → mean_xg), CRN confirm stage + CIs, anti-exploit boundary/face-validity
  flags. No Optuna/LightGBM/SHAP/MLflow/IO.
- **Driver** (`restart_opt`, new package): Optuna TPE screen + random baseline, confirm
  orchestration, study persistence, MLflow logging, LightGBM surrogate + SHAP, sensitivity
  analysis, canonical study, CLI. Loads the committed xG bundle JSON (pure `XGModelBundle.from_dict`)
  and injects an xG-enabled engine into the runner.

---

## 4. Pure core additions - `packages/simulation-core/src/restart/optimize/`

### 4.1 `genome.py`
- Param types (frozen dataclasses): `ContinuousParam(name, lo, hi)` (exists, move here),
  `IntParam(name, lo, hi)`, `CategoricalParam(name, choices: tuple[str, ...])`. Common protocol
  for `validate(value)`.
- `SearchSpace(params: tuple[Param, ...])` - `validate(values)` dispatches per param type;
  `bounds()` accessor for the driver to build suggestions.
- `ZONE_GRID: dict[str, PitchPoint]` - fixed named box zones (near/far post, six-yard L/R,
  penalty spot, goalmouth, edge). Targets for runner final legs; keeps dimensionality sane vs raw
  coordinates (doc 06 §3.1).
- `CornerGenome`:
  - `space() -> SearchSpace` - the ~10-15-dim corner search space.
  - `to_scenario(base: Scenario, values: Mapping[str, ...]) -> Scenario` - pure builder over a
    fixed corner template (N runners, default 4). Maps delivery params + per-runner
    (zone, delay, intent) into a `RoutineSpec`, then a `Scenario`. **Raises `ValueError` on an
    infeasible combination** (spec validation rejects, never repairs - ADR-004 d2; the optimizer
    sees a failure, not a crash).

### 4.2 objective (extend `interfaces.py` / new `objective.py`)
- **Objective = mean xG per sim** (doc 06 §2.3) - replaces the current `p_goal` return value.
- `EvaluationResult` carries: `mean_xg`, `mean_xg_ci_lo/hi`, `p_goal`, `n_sims`, `root_seed`,
  `counterattack_risk` (reported, not optimized).
- `RoutineObjective` takes a genome + base scenario + an **xG-enabled runner** (driver injects it);
  `__call__(values) -> float` returns `mean_xg`. Deterministic per (values, root_seed) - CRN ready.
- `counterattack_risk` = pure read of existing outcomes: fraction of sims ending in defensive
  recovery (`SECOND_BALL_DEFENSE`, plus defense-controlled `CLEARED`). No engine change. Documented
  as a proxy.

### 4.3 `confirm.py` (pure)
- `mean_xg_samples(batch) -> np.ndarray` - per-sim xG contribution (shot xg or 0.0).
- `mean_ci(samples, alpha=0.05) -> (mean, lo, hi)` - normal/t interval (scipy); valid at confirm
  budgets (n ≥ ~1000).
- `confirm_candidates(make_objective, candidates, n_confirm, root_seed) -> list[ConfirmResult]` -
  re-evaluates each candidate at `n_confirm` sims using a **common root_seed (CRN)**.
- `beats_baseline(candidate_ci, baseline_ci) -> bool` - non-overlapping 95% CIs.

### 4.4 `boundary.py` (pure anti-exploit)
- `boundary_flags(space, values, eps_frac=0.02) -> list[str]` - continuous/int params within ε of
  a bound (categoricals N/A).
- `face_validity_flags(result, mean_xg_ceiling=0.5) -> list[str]` - flags implausibly high
  mean_xg (real corner mean xG is far below this) and other cheap sanity rules. Optimizers find
  simulator bugs before football insights (doc 06 §3.2).

`restart/optimize/__init__.py` re-exports the public surface; backward-compatible aliases kept
where the existing `corner_delivery_space`/`RoutineObjective` names are imported by tests.

**Existing-test compatibility:** `test_montecarlo.py::TestOptimizationInterface` asserts the
objective is deterministic and returns a value in `[0,1]`. `mean_xg ∈ [0,1]` satisfies this; with
the default (no-xG) runner `mean_xg = 0.0` for all params, which still passes those assertions.
Those tests are updated to the mean_xg semantics where they assert intent, not just bounds.

---

## 5. New package - `packages/optimizer/` (`restart_opt`)

Layout mirrors `packages/ml`:

```
packages/optimizer/
  pyproject.toml            # deps: numpy, optuna, lightgbm, shap, mlflow, restart-simulation-core
  src/restart_opt/
    __init__.py             # OPT_VERSION = "0.1.0"
    bundle.py               # load committed models/xg-v1.json -> XGModelBundle (pure from_dict); build xG engine + runner
    study.py                # run_study(): Optuna TPE + MedianPruner screen; random-search baseline at equal budget
    confirm.py              # orchestrate core confirm on top-k; compare to library baseline
    persist.py              # study + trials -> optimization_studies/<name>/ JSON (artifacts.py style)
    mlflow_log.py           # mirror train.py: sqlite backend, one run per study
    surrogate.py            # LightGBM on (encoded genome -> mean_xg) + SHAP -> insights JSON/MD
    sensitivity.py          # ±10% curated-attribute perturbation, re-rank top-k, class-vs-precise verdict
    canonical.py            # England corners vs Argentina zonal (demo squads; squad-from-marts is P6)
    cli.py                  # restart-opt: study run | confirm | insights | sensitivity | canonical | version
  tests/                    # see §6
```

- **Optuna determinism:** `TPESampler(seed=...)`, random sampler seeded. Infeasible genome →
  driver catches `ValueError` → `optuna.TrialPruned` (core stays optuna-agnostic).
- **Persistence:** JSON (sorted keys, trailing newline) under `optimization_studies/<study>/`:
  `study.json` (config + best + comparison) and `trials.jsonl`. `optimization_studies/` is
  git-ignored except a committed canonical study artifact (small) for the writeup.
- **MLflow:** experiment `optimizer`; params (genome dims, budget, seeds, engine_version, git SHA),
  metrics (best screen/confirm mean_xg, TPE-vs-random delta), study artifact path.
- **Surrogate insights:** SHAP top contributors → templated plain-language strings (e.g. "against
  this zonal line, delivery 2 m beyond far-post + late near-post decoy ≈ +0.0X mean xG").
- **Sensitivity:** perturb the curated/derived attributes (doc 04 §3: heading, jump reach,
  delivery, etc.) ±10%; if top-k ranking order flips, the writeup reports routine **classes**, not
  player-precise picks (roadmap R9).

---

## 6. Tests (TDD - write first)

Core (simulation-core/tests):
- `test_optimize_genome.py` - `to_scenario` yields a valid `Scenario` for sampled params; each
  param type validates/rejects; infeasible combo raises `ValueError`; zone grid points on-pitch.
- `test_optimize_objective.py` - objective returns mean_xg ∈ [0,1]; deterministic per
  (params, seed); CRN: same root_seed → bit-identical, different seed may differ;
  counterattack_risk ∈ [0,1].
- `test_optimize_confirm.py` - `mean_ci` brackets the mean; `beats_baseline` correct on synthetic
  non-overlapping vs overlapping CIs; `confirm_candidates` CRN-deterministic.
- `test_optimize_boundary.py` - boundary flag catches edge param, ignores interior;
  face-validity flag catches implausible mean_xg.

Driver (optimizer/tests):
- `test_study_toy.py` - inject an engine-free **planted-optimum** objective (Gaussian over the
  search space) via the `ObjectiveFunction` protocol; TPE recovers the optimum at least as well as
  random at equal small budget; random-search-beats-nothing sanity. Fast (no engine sims).
- `test_study_determinism.py` - same seed ⇒ identical trial sequence/best (tiny engine budget).
- `test_persist.py` - study round-trips to JSON and back.
- `test_surrogate.py` - LightGBM + SHAP on a tiny synthetic trial set produce finite contributions
  (seeded, deterministic).
- `test_sensitivity.py` - perturbation harness returns a stable/unstable verdict on a toy ranking.

---

## 7. Config & workspace wiring

- Root `pyproject.toml`: add `packages/optimizer` to `tool.uv.workspace.members`,
  `tool.uv.sources`, `tool.ruff.src`, `tool.mypy.mypy_path`/`files`, `tool.pytest.testpaths`;
  add `restart-optimizer` to root deps.
- mypy overrides: add `optuna.*`, `shap.*` (and `cmaes.*` if later) to `ignore_missing_imports`
  (lightgbm/mlflow already present).
- `.gitignore`: `optimization_studies/` (re-include the one committed canonical artifact, mirroring
  the `models/*.json` precedent).
- Reproduction (doc 06 §4): no Makefile exists, so `restart-opt canonical --seed N` is the
  documented one-command rebuild of any shipped study number.

---

## 8. Documentation deliverables

- `docs/09-optimization-methodology.md` (07=UI/UX, 08=roadmap are taken) - search space, screen-then-confirm,
  CRN, anti-exploit, surrogate/SHAP, sensitivity; the reference vs committed budget honesty.
- `docs/case-studies/england-vs-argentina.md` - canonical study writeup (becomes the case-study
  centerpiece): setup, budget used, TPE-vs-random, confirmed top routine vs library baseline (CIs),
  ≥3 insights, sensitivity verdict, anti-exploit review.
- Update `docs/handoff/*` (PROJECT_STATUS, PHASE_HANDOFF, ADR_SUMMARY + new ADR-006 for System B,
  ASSUMPTIONS_REGISTER, TECHNICAL_DEBT), `CHANGELOG.md` (Unreleased), `docs/08-roadmap.md` status.

---

## 9. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Engine too slow for meaningful study | Scoped configurable budget (D1); optional parallelism; honest documentation; kernel debt carried forward. |
| Optimizer exploits sim artifacts | Anti-exploit boundary + face-validity flags; face-validity review of top-k in the writeup. |
| TPE underperforms on categorical-heavy space | Mandatory random-search baseline at equal budget catches it honestly. |
| Attribute priors dominate rankings | ±10% sensitivity analysis; report routine classes if rankings flip. |
| Infeasible genome combinations | `to_scenario` raises `ValueError`; driver prunes; tested. |
| Pure-domain violation | All Optuna/ML/IO isolated in `restart_opt`; core import-clean (verified by gates + review). |

---

## 10. Out of scope (this phase)

- Fused Numba scenario kernel (carried-forward 🔴 debt).
- CMA-ES / GA comparison studies (Tier-2, future).
- Multi-objective optimization (counterattack reported only).
- Engine upstream `[knob]` calibration (separate owed gate; data now in hand).
- Squad selection from marts (Phase 6; canonical study uses demo squads).
- Frontend optimization UI (Phase 7).

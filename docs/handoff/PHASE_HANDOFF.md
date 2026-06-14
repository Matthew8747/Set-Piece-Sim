# Phase Handoff

> Rewritten at the end of every completed phase.

## Last completed phase: Phase 5 — Optimization engine, System B (`restart_opt 0.1.0`)

### What shipped
- **Pure optimize core (`restart.optimize`)** — IO/ML-free, in the simulation core:
  `genome.py` (typed mixed search space `ContinuousParam`/`IntParam`/`CategoricalParam`; the
  ~13-dim `CornerGenome` over a fixed runner template + zone grid, with the genotype→`Scenario`
  builder that raises on infeasible specs; `DeliveryGenome` keeps the v1 delivery sub-space);
  the `RoutineObjective` now returns **mean xG per sim** (deterministic per (params, root_seed) for
  common random numbers) and reports counterattack risk without optimizing it; `confirm.py`
  (mean-xG CI, non-overlap decision rule, CRN confirm stage); `boundary.py` (anti-exploit
  bound-pinning + face-validity ceiling).
- **`optimizer` package (`restart_opt`, CLI `restart-opt`)** — all Optuna/LightGBM/SHAP/MLflow + IO,
  isolated from the core: `study.py` (seeded Optuna TPE + mandatory random baseline; infeasible →
  pruned, not crashed), `screen.py` (engine-backed screen with CRN + median pruning, confirm
  orchestration vs the library baseline), `bundle.py` (loads the committed xG bundle via the pure
  `from_dict` — no `restart_ml` dep), `surrogate.py` (LightGBM + SHAP → plain-language insights),
  `sensitivity.py` (±10% curated-attribute perturbation → routine-precise vs report-classes),
  `persist.py` + `mlflow_log.py` + `canonical.py` + `cli.py`.
- **Canonical study:** *England corners vs Argentina zonal* (`restart-opt canonical`), persisted to
  `optimization_studies/england-vs-argentina/study.json` and logged to MLflow. Demo squads
  (mart-derived squads are Phase 6).
- Docs: [ADR-006](../adr/ADR-006-routine-optimizer.md),
  [optimization methodology](../09-optimization-methodology.md),
  [the case-study writeup](../case-studies/england-vs-argentina.md);
  [CHANGELOG](../../CHANGELOG.md) Phase-5 entry. `ENGINE_VERSION` **unchanged** (`sim/0.4.0`).

### Validation evidence
All gates green (ruff, black, mypy --strict, pytest, next build, eslint, tsc, prettier, vitest).
Optimizer-specific tests: planted-optimum recovery on a toy landscape with TPE **>** random at equal
budget (6-D); CRN bit-identical determinism (objective, screen, confirm); infeasible-genome pruning;
anti-exploit boundary + face-validity flags; mean-xG CI + non-overlap rule; LightGBM+SHAP surrogate
recovers the driving feature; sensitivity verdict logic; end-to-end canonical smoke. Quantitative
study results (TPE-vs-random, winner-vs-baseline CIs, insights, sensitivity verdict) are in the
case-study writeup.

### Debugging history worth knowing (saves future sessions time)
1. **Throughput is the real constraint, measured.** Reference engine ≈ **3 sims/s** with xG wired
   (not the ~30–80 ms/sim the runner docstring suggested — that predates the xG path). The full
   reference budget (500 screen / 10k confirm / top-5 + equal random) ≈ 14 h and cannot run in CI;
   budgets are scoped + configurable and the kernel is deferred (ADR-006).
2. **Pure-domain forces the package split.** Optuna persistence (SQLite/JSON), MLflow, and
   LightGBM+SHAP are all IO/ML, so they cannot live in `restart.optimize`. The pure contracts stay
   in the core; the engine lives in `restart_opt`. (Confirms doc-06's "optimize is the home" — for
   the *pure* surface.)
3. **`Param` protocol vs frozen dataclasses.** mypy rejected `name: str` as a settable Protocol
   member against frozen dataclass attributes; declare it as a read-only `@property` in the Protocol.
4. **TPE-beats-random is landscape-dependent.** On a smooth 2-D peak random search is a strong
   baseline (doc 06 says so); the advantage is robust in higher dims, so the unit test asserts it on
   a 6-D landscape and keeps planted-optimum recovery as the 2-D guarantee.
5. **SHAP encoding is pandas-free** (pandas fights mypy --strict): integer-code categoricals, pass
   their indices to LightGBM, attribute SHAP per original feature.

### Open decisions carried forward
- **Fused Numba scenario kernel (🔴):** the path to 10⁵–10⁶-sim studies; deferred from P5 to keep
  the phase tractable. Until it lands, studies are budget-limited (documented).
- **Engine upstream `[knob]` calibration (🔴, still owed from P3/P4):** the simulated shot-context
  *distribution* is unvalidated (goal ~5% sim vs 2–3% real); `mart_calibration_targets` holds the
  real base rates to fit against.
- **Demo squads:** the canonical study uses demo squads; mart-derived squad selection is Phase 6.
- **CMA-ES / GA comparison + multi-objective (xG vs counterattack):** documented future work.

## Next phase: Phase 6 — API & Scenario Workbench (roadmap weeks 9–10)

Scope: FastAPI surface (validation, rate limiting, API keys, problem-details, OpenAPI), Arq worker +
progress, idempotency, the `pitch-kit` (SVG pitch, replay player, charts), the Scenario Workbench
(Build/Simulate/Replay), Playwright E2E of the 3-minute journey. Wire **mart-derived squads** from
`mart_players`/`mart_player_attributes` (replacing demo squads) and the Postgres loaders + persistence.

### Risks for Phase 6
1. Frontend scope explosion — the workbench is 80% of UI value; everything else is cuttable.
2. Pitch-editor interaction polish is a time sink → snap-to-grid + constrained handles over
   free-form gestures.
3. Squad-from-marts wiring touches the API/persistence boundary not yet built (tech-debt P6).

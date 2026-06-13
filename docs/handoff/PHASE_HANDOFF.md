# Phase Handoff

> Rewritten at the end of every completed phase.

## Last completed phase: Phase 3 — Monte Carlo, analytics & MVP (`sim/0.3.0`)

### What shipped
- `restart.montecarlo`: `MonteCarloRunner` (seeded batches), `aggregate`/`OutcomeStats` (Wilson
  CIs via SciPy), `build_report`/`SimulationReport` (serializable, the API/UI payload).
- `restart.optimize`: interfaces only — `SearchSpace`, `ContinuousParam`, `ObjectiveFunction`
  protocol, `RoutineObjective`, `corner_delivery_space()`. No optimizers (Phase 5).
- Backend: `apps/backend/.../routers/v1/setpieces.py` (catalog/simulate/montecarlo, n_sims
  bounded), DTOs in `schemas.py`.
- Frontend: `apps/frontend/src/{lib/api.ts, components/Pitch.tsx, components/Workbench.tsx,
  app/workbench/page.tsx}`. shared-types DTO mirrors added.
- Details: [CHANGELOG](../../CHANGELOG.md) Phase-3 entry.

### Validation evidence
413 tests green (410 py + 3 fe). mypy --strict, ruff, black, eslint, tsc, prettier, next build
all clean. Live boot confirmed: `/api/v1/setpieces/routines` → 200 (5 routines);
simulate/montecarlo round-trip deterministic per seed over HTTP.

### Debugging history worth knowing (saves future sessions time)
1. Reference engine measured ~2–3 sims/s; the dominant cost was `np.cross` (moveaxis overhead)
   inside the per-step force eval and `separate()` scanning all 231 pairs every tick. Both
   rewritten (equivalence-preserving). The ball-flight horizon cap (4 s) cut roll-to-rest tails.
   The *real* 100k answer is the fused Numba scenario kernel (ADR-003 d8), not micro-opt of the
   reference engine — don't rabbit-hole optimizing the reference.
2. `ruff --fix` stripped a `# noqa: UP047` on `tactics/compile._ro`; converted it to PEP 695
   `def _ro[A: npt.NDArray[np.generic]](arr: A) -> A` and dropped the dead `_AnyArray` TypeVar.
3. ESLint "setState in effect": Pitch resets replay state by **remount key**
   (`<Pitch key=... />` in Workbench), not a reset effect.

### Open decisions carried forward
- Calibration still owed (engine `[knob]`s vs real base rates) — the roadmap week-5 credibility
  gate, deferred behind the MVP per the product-owner directive. Goal rate ~5% vs 2–3% real.
- Fused batch scenario kernel deferred (reference engine adequate for MVP batch sizes ≤ ~1000).

## Next phase: Phase 4 — Data platform, player profiles, xG v1 (roadmap §Phase 4)

Scope: `etl` package (StatsBomb Open Data → raw → staging → marts; license gate in CI),
`mart_setpiece_shots`, derived provenance-tagged player attributes for launch teams, xG models
(LR baseline + GBM sweep, grouped-by-match CV, calibration), MLflow, simulator integration
(engine emits shot contexts → real-data xG scores them instead of the placeholder GK/aim model).

### Risks for Phase 4
1. Set-piece shot sample size (measure first — design doc 04 §2); feature plan degrades
   gracefully if freeze-frame coverage is thin.
2. Licensing: no scraped ratings (EA/sofifa forbidden); StatsBomb attribution; the CI license
   gate must be mechanical (doc 04 §5).
3. xG↔engine circularity trap: xG trains on REAL data only (design doc 06 §1) — never on
   simulator output.

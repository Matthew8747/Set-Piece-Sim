# Phase 7 — Optimization UI & 3D Replay — Design

**Status:** Approved · **Engine:** `sim/0.4.0` (unchanged — UI/read-API phase, no physics) ·
**Branch:** `feat/phase7-optimization-ui` (off `main` @ `dd29ce4`, PR #6 merged)

## 1. Goal

Surface the persisted optimization study as a coach-facing analytical surface, add the
common-random-number compare mode to the workbench, and add on-demand 3D replay — all over data and
transports that already exist. No engine changes, no search runs in the request path.

## 2. Hard boundary (the ADR-008 core)

`restart_opt` (Optuna / LightGBM / SHAP / MLflow) **never enters the API runtime**. The web process
reads the persisted `optimization_studies/<slug>/study.json` as **data** — a JSON parse into typed
DTOs, never an import of the optimizer package (extends ADR-006). A test asserts `restart_opt` is not
importable from the running app context. `ENGINE_VERSION` stays `sim/0.4.0`; determinism preserved;
no scraped ratings; charts are hand-rolled SVG (visx peers still cap at React 18, ADR-007 d7) except
React Three Fiber for the 3D view.

## 3. Data already in hand (verified)

- `study.json` keys: `baseline`, `config`, `confirm` (top-k, 16-param genomes + CI), `created_at`,
  `engine_version`, `feature_importance` (SHAP), `insights` (3 plain-language strings), `matchup`
  (`attacking`/`defending`/`scheme`), `name`, `opt_version`, `random`/`tpe` (each: `best_params`,
  `best_value`, `n_trials`, `sampler`, `seed`, `trials[]`), `sensitivity` (`verdict`, `top1_stable`,
  `rankings_flip`, `flipped`, `frac`, `baseline_order`), `winner` (`mean_xg`, `ci`, `beats_baseline`,
  `boundary_flags`, `face_validity_flags`, `params`).
- Each trial: `{params, state, value}` where `value` = mean xG. Best-so-far = cumulative max over
  trial order.
- `SimulateResponse.ball_path` is `(samples, 3)` — the ball trajectory already carries `z`, so 3D
  gets a real arc. Player tracks are `(T, n, 2)` → ground-plane markers. `pitch-kit` `Point` already
  allows `[x, y, z]`.
- Determinism contract (`restart/montecarlo/runner.py`): `sim_seeds(root_seed, n)` =
  `SeedSequence(root_seed).generate_state(n)` is **scenario-independent**. Two scenarios run at the
  same `seed` + `n_sims` therefore share the per-sim seed stream → common-random-number pairing is
  free; the paired per-sim xG difference is valid with no new sim compute.

## 4. Milestones

Each milestone ends green on `scripts/verify.ps1` (incl. OpenAPI/shared-types drift) and is a
self-contained commit. Review checkpoints after M3 and M4.

### M1 — Read-only optimization API
- `restart_api/studies/loader.py` — `StudyLoader` reads `optimization_studies/*/study.json` as data
  (mirrors `MartSquadLoader` injection pattern). `settings.studies_dir = Path("optimization_studies")`.
- Pure derivation helpers (typed, tested): cumulative-max best-so-far series for `tpe` and `random`;
  per-axis metadata for parallel-coords (axis name, `continuous`/`categorical`, numeric domain or
  category order, SHAP importance for ordering).
- DTOs + routes:
  - `GET /api/v1/optimizations` → `OptimizationSummaryDTO[]` (`id`/slug, `name`, `matchup`,
    `engine_version`, `created_at`, winner `mean_xg` + `ci`, `beats_baseline`, `n_trials`, `stale`).
  - `GET /api/v1/optimizations/{id}` → `OptimizationDetailDTO` (convergence series, trials + axis
    meta, top-k confirm vs baseline, `feature_importance`, `insights`, `sensitivity`, `winner`).
- `stale` = study `engine_version` ≠ current `ENGINE_VERSION` (flagged, never a failure).
- Regenerate `openapi.json` + shared-types; drift gate green.
- Tests: loader (missing/malformed → 404/problem-detail), derivations, endpoint contract,
  stale-flag, **`restart_opt`-not-imported** guard.

### M2 — pitch-kit optimization SVG primitives (hand-rolled, React 19, vitest each)
- `ConvergencePlot` — best-so-far step lines for TPE vs random baseline; winner confirm ± CI shaded
  band; library-baseline reference line; IBM Plex Mono tabular axes; doc-07 tokens.
- `ParallelCoordinates` — one polyline per trial across mixed axes (continuous normalized to axis
  domain; categorical laddered by category order); stroke opacity/hue by trial xG; hover/brush
  highlight; axes ordered by SHAP importance; color-blind-safe; `prefers-reduced-motion` static.
- `TopKTable` — top-k confirm vs baseline with CI whiskers, beats-baseline marker, bound-pinning /
  face-validity flag chips.
- Exported from `index.ts`.

### M3 — `/optimize` + `/optimize/:id` pages  *(review checkpoint)*
- `api.ts`: `optimizations()`, `optimization(id)`.
- `/optimize` — study library cards: matchup, winner `mean_xg ± ci`, beats-baseline badge **only**
  when CIs are non-overlapping, `n_trials`, engine version + stale flag, determinism chrome.
- `/optimize/:id` — `ConvergencePlot` + `ParallelCoordinates` + `TopKTable` + plain-language SHAP
  **insights panel** (`study.insights`) + sensitivity honesty banner ("reporting routine *classes*"
  when `rankings_flip`). "How?" affordances link to `docs/09-optimization-methodology.md`.
- frontend vitest + `next build` green.

### M4 — Workbench compare mode  *(review checkpoint)*
- In `/scenarios/:id`: pick scenario B (routine/scheme). Run both via existing `/sim-runs` at
  **identical seed + n_sims** (UI-enforced; mismatched config blocks the compare).
- `compareStats` pure fn (unit-tested): consumes both runs' per-sim `xg_samples`, computes the
  **paired** per-sim difference and a large-sample CI on the mean difference.
- Overlay both xG distributions on a **shared x-scale** (deception-trap avoided).
- Winner badge shown **only if** the paired-difference CI excludes 0; otherwise "no significant
  difference." The pure fn + its test *are* the doc-07 §5.4 / Sim-Architecture §5.4 stats-policy
  enforcement.

### M5 — 3D replay (R3F, dynamic-imported, load-on-demand)
- `Replay3D` consumes the **same** `SimulateResponse`: `ball_path` → 3D arc; `att_tracks`/
  `def_tracks` → ground-plane markers. Camera presets: broadcast / behind-goal / GK.
- `2D ⇄ 3D` toggle in `ReplayPanel`; 2D stays the default and the SVG-only fallback.
- R3F loaded via dynamic `import()` so it never enters the default chunk (verified). Reduced-motion
  honored (static framed view, no auto-orbit).
- New deps `@react-three/fiber` + `three` (+ `@types/three`) in **apps/frontend only**. No new
  Python deps → mypy config untouched.

### M6 — Docs, ADR-008, handoff + PR
- **ADR-008** "Read-only optimization surface & 3D replay transport": the data-only boundary
  (extends ADR-006), CRN compare pairing via the seeding contract + no-winner-without-significance,
  3D over the existing replay JSON, charts-still-hand-rolled (visx React-18-capped), `/teams`
  deferred to Phase 7.x.
- Close 🟡 "No 3D visualization" in `TECHNICAL_DEBT.md`. Update `PROJECT_STATUS.md`, `CHANGELOG.md`,
  frontend README; rewrite `PHASE_HANDOFF.md`. PR → `main`.

## 5. Explicitly out of scope (Phase 7.x / later)
- `/teams` team-intelligence (squad aerial/pace profiles, mismatch matrix) and `/reports` export.
- Any optimizer *run* from the browser; any new study generation.
- Carried-forward 🔴 debt (engine `[knob]` calibration, fused Numba kernel) and O-3 fidelity — future
  engine phases, untouched here.

## 6. Risks
1. **R3F bundle weight** → dynamic import only; 2D default + SVG fallback; verify R3F absent from the
   default chunk.
2. **Parallel-coords legibility with mixed types** → categorical axes laddered with explicit category
   order; axis order by SHAP importance; brush to isolate. Build it as the "wow" view, test the
   normalization math.
3. **Honesty caps** — the carried 🔴 calibration means any "winner" stays a routine *class*; the
   sensitivity banner and the no-significance-no-badge rule keep claims honest.
4. **`xg_samples` availability** — compare mode depends on per-sim `xg_samples` in `SimRunStatus`;
   confirm in M4's first test before building the UI.

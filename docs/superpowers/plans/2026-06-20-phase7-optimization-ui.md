# Phase 7 — Optimization UI & 3D Replay — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the persisted optimization study (`study.json`) as a read-only API + `/optimize`
pages, add CRN compare mode to the workbench, and add on-demand R3F 3D replay — over existing data
and transports, no engine change.

**Architecture:** `restart_opt` stays out of the API runtime — the web process reads
`optimization_studies/<slug>/study.json` as **data** (typed DTOs, no optimizer import; extends
ADR-006). Charts are hand-rolled SVG in `@restart/pitch-kit` (visx still React-18-capped, ADR-007 d7)
except React Three Fiber for 3D. Compare mode exploits the scenario-independent `sim_seeds` contract
for free common-random-number pairing. `ENGINE_VERSION` unchanged (`sim/0.4.0`).

**Tech Stack:** FastAPI + Pydantic (backend), Next 16 / React 19 + TypeScript (frontend),
`@restart/pitch-kit` SVG primitives, `@react-three/fiber` + `three` (3D only), vitest + pytest +
Playwright, `scripts/verify.ps1` gate (incl. OpenAPI/shared-types drift).

**Verify gate (run after every milestone):** `pwsh scripts/verify.ps1` must be green.
Spec: `docs/superpowers/specs/2026-06-20-phase7-optimization-ui-design.md`.

---

## File Structure

**Backend (M1)**
- Create `apps/backend/src/restart_api/studies/__init__.py`
- Create `apps/backend/src/restart_api/studies/loader.py` — `StudyLoader` (data-only), pure
  derivations (best-so-far, axis meta), study→DTO mapping.
- Modify `apps/backend/src/restart_api/settings.py` — add `studies_dir: Path`.
- Modify `apps/backend/src/restart_api/deps.py` — add `study_loader()` accessor.
- Create `apps/backend/src/restart_api/routers/v1/optimizations.py` — two GET routes.
- Modify `apps/backend/src/restart_api/routers/v1/__init__.py` — include router.
- Modify `apps/backend/src/restart_api/schemas.py` — optimization DTOs.
- Create `apps/backend/tests/test_optimizations.py`.

**pitch-kit (M2)**
- Create `packages/pitch-kit/src/charts/ConvergencePlot.tsx`
- Create `packages/pitch-kit/src/charts/ParallelCoordinates.tsx`
- Create `packages/pitch-kit/src/charts/TopKTable.tsx`
- Modify `packages/pitch-kit/src/index.ts` — export the three.
- Modify `packages/pitch-kit/src/charts/charts.test.tsx` (or new `optimization.test.tsx`).

**Frontend optimize pages (M3)**
- Modify `apps/frontend/src/lib/api.ts` — `optimizations()`, `optimization(id)`.
- Create `apps/frontend/src/app/optimize/page.tsx` — study library.
- Create `apps/frontend/src/app/optimize/[id]/page.tsx` — study host.
- Create `apps/frontend/src/components/optimize/StudyDetail.tsx`, `InsightsPanel.tsx`,
  `SensitivityBanner.tsx`.
- Tests: `apps/frontend/src/components/optimize/*.test.tsx`.

**Compare mode (M4)**
- Create `apps/frontend/src/lib/compareStats.ts` — pure paired-difference CI.
- Create `apps/frontend/src/lib/compareStats.test.ts`.
- Modify `apps/frontend/src/components/workbench/SimulatePanel.tsx` (or new `ComparePanel.tsx`).

**3D replay (M5)**
- Create `packages/pitch-kit/src/Replay3D.tsx` (R3F) + barrel note (NOT in `index.ts` default
  export path used by 2D — exported separately to keep dynamic-import isolation).
- Modify `apps/frontend/src/components/workbench/ReplayPanel.tsx` — `2D⇄3D` toggle + `dynamic()`.
- Add deps to `apps/frontend/package.json`: `@react-three/fiber`, `three`, `@types/three`.

**Docs (M6)**
- Create `docs/adr/ADR-008-optimization-surface-and-3d-replay.md`.
- Modify `docs/handoff/{PHASE_HANDOFF,PROJECT_STATUS,TECHNICAL_DEBT}.md`, `CHANGELOG.md`,
  `apps/frontend/README.md`, `docs/07-ui-ux-design.md` (IA tick).

---

## Milestone 1 — Read-only optimization API

### Task 1.1: Settings — `studies_dir`

**Files:** Modify `apps/backend/src/restart_api/settings.py`; Test `apps/backend/tests/test_settings.py`

- [ ] **Step 1 — failing test** (append to `test_settings.py`):
```python
def test_studies_dir_defaults_to_optimization_studies():
    from restart_api.settings import Settings
    assert Settings().studies_dir == Path("optimization_studies")
```
- [ ] **Step 2 — run, expect fail:** `uv run pytest apps/backend/tests/test_settings.py -q` → AttributeError/`studies_dir`.
- [ ] **Step 3 — implement:** add under `data_dir` in `Settings`:
```python
    # Where persisted optimizer studies live. Read-only: the API loads study.json
    # as DATA — restart_opt is never imported in the request path (ADR-006/008).
    studies_dir: Path = Path("optimization_studies")
```
- [ ] **Step 4 — run, expect pass.**
- [ ] **Step 5 — commit:** `git add -A && git commit -m "feat(api): studies_dir setting for read-only optimization surface"`

### Task 1.2: Optimization DTOs

**Files:** Modify `schemas.py`; Test `apps/backend/tests/test_optimizations.py` (new)

DTO contract (add to `schemas.py`):
```python
class ConvergencePointDTO(BaseModel):
    trial: int          # 1-based trial index
    best_so_far: float  # cumulative-max mean xG up to this trial

class AxisDTO(BaseModel):
    name: str
    kind: Literal["continuous", "categorical"]
    domain: list[float] | None = None      # [min, max] for continuous
    categories: list[str] | None = None    # order for categorical ladder
    importance: float                       # SHAP importance (0 if absent)

class TrialDTO(BaseModel):
    params: dict[str, float | str]
    value: float
    state: str

class ConfirmRowDTO(BaseModel):
    params: dict[str, float | str]
    mean_xg: float
    ci_lo: float
    ci_hi: float
    n_sims: int

class WinnerDTO(BaseModel):
    mean_xg: float
    ci: list[float]
    beats_baseline: bool
    boundary_flags: list[str]
    face_validity_flags: list[str]

class SensitivityDTO(BaseModel):
    verdict: str
    top1_stable: bool
    rankings_flip: bool
    flipped: list[str]

class MatchupDTO(BaseModel):
    attacking: str
    defending: str
    scheme: str

class OptimizationSummaryDTO(BaseModel):
    id: str
    name: str
    matchup: MatchupDTO
    engine_version: str
    created_at: str
    winner_mean_xg: float
    winner_ci: list[float]
    beats_baseline: bool
    n_trials: int
    stale: bool   # study engine_version != current ENGINE_VERSION

class OptimizationDetailDTO(BaseModel):
    id: str
    name: str
    matchup: MatchupDTO
    engine_version: str
    created_at: str
    stale: bool
    convergence_tpe: list[ConvergencePointDTO]
    convergence_random: list[ConvergencePointDTO]
    baseline_mean_xg: float
    baseline_ci: list[float]
    trials: list[TrialDTO]
    axes: list[AxisDTO]
    confirm: list[ConfirmRowDTO]
    feature_importance: dict[str, float]
    insights: list[str]
    sensitivity: SensitivityDTO
    winner: WinnerDTO
```
- [ ] **Step 1 — failing test** (`test_optimizations.py`):
```python
from restart_api.schemas import OptimizationDetailDTO, OptimizationSummaryDTO  # noqa: F401
def test_optimization_dtos_importable():
    assert OptimizationSummaryDTO.model_fields["stale"]  # type: ignore[truthy-bool]
```
- [ ] **Step 2 — run, expect fail** (ImportError).
- [ ] **Step 3 — implement** the DTOs above (ensure `Literal` imported).
- [ ] **Step 4 — run, expect pass.**
- [ ] **Step 5 — commit:** `feat(api): optimization study DTOs`

### Task 1.3: StudyLoader + pure derivations (data-only)

**Files:** Create `studies/__init__.py`, `studies/loader.py`; Test `test_optimizations.py`

`loader.py` responsibilities (no `restart_opt` import — `json.load` only):
- `class StudyLoader` ctor `(studies_dir: Path)`.
- `list_summaries() -> list[OptimizationSummaryDTO]` — glob `*/study.json`, id = parent dir name.
- `get_detail(study_id: str) -> OptimizationDetailDTO` — raise `KeyError` if absent (router → 404).
- Pure helpers (module-level, individually tested):
  - `best_so_far(trials: list[dict]) -> list[ConvergencePointDTO]` — cumulative max of `value` over
    list order, 1-based `trial`.
  - `axes_from(trials, feature_importance) -> list[AxisDTO]` — for each param key across trials:
    numeric → `continuous` with `domain=[min,max]`; str → `categorical` with sorted unique
    `categories`; `importance = feature_importance.get(name, 0.0)`; sort axes by importance desc.
  - `_stale(study_engine: str) -> bool` — `study_engine != ENGINE_VERSION`.

- [ ] **Step 1 — failing tests:**
```python
import json
from pathlib import Path
from restart_api.studies.loader import StudyLoader, best_so_far, axes_from

REAL = Path("optimization_studies")  # committed canonical study

def test_best_so_far_is_cumulative_max():
    trials = [{"value": 0.1}, {"value": 0.3}, {"value": 0.2}, {"value": 0.5}]
    series = best_so_far(trials)
    assert [p.best_so_far for p in series] == [0.1, 0.3, 0.3, 0.5]
    assert [p.trial for p in series] == [1, 2, 3, 4]

def test_axes_split_continuous_and_categorical():
    trials = [
        {"params": {"speed_ms": 22.0, "delivery_type": "inswinger"}},
        {"params": {"speed_ms": 25.0, "delivery_type": "floated"}},
    ]
    axes = {a.name: a for a in axes_from(trials, {"speed_ms": 0.4, "delivery_type": 0.1})}
    assert axes["speed_ms"].kind == "continuous" and axes["speed_ms"].domain == [22.0, 25.0]
    assert axes["delivery_type"].kind == "categorical"
    assert set(axes["delivery_type"].categories) == {"inswinger", "floated"}

def test_loader_reads_canonical_study_as_data():
    detail = StudyLoader(REAL).get_detail("england-vs-argentina")
    assert detail.matchup.attacking and len(detail.trials) == detail_n(detail)
    assert detail.winner.beats_baseline in (True, False)
    assert len(detail.convergence_tpe) == len(detail.trials)

def detail_n(d):  # tpe trial count
    return len(d.trials)

def test_unknown_study_raises_keyerror():
    import pytest
    with pytest.raises(KeyError):
        StudyLoader(REAL).get_detail("does-not-exist")
```
- [ ] **Step 2 — run, expect fail** (module missing).
- [ ] **Step 3 — implement** `loader.py` + `__init__.py`. Map `study["tpe"]["trials"]` → `trials`/
  `convergence_tpe`; `study["random"]["trials"]` → `convergence_random`; `confirm[]` →
  `ConfirmRowDTO`; pass through `feature_importance`, `insights`, `sensitivity`, `winner`,
  `baseline`. **No `import restart_opt`.**
- [ ] **Step 4 — run, expect pass.**
- [ ] **Step 5 — commit:** `feat(api): StudyLoader reads study.json as data + pure derivations`

### Task 1.4: deps accessor + router + wiring

**Files:** Modify `deps.py`, `routers/v1/optimizations.py` (new), `routers/v1/__init__.py`

- `deps.py`: add
```python
def study_loader() -> StudyLoader:
    return StudyLoader(get_settings().studies_dir)
```
  (mirror the existing `team_repository()` accessor style; import `StudyLoader`, `get_settings`).
- `optimizations.py`:
```python
from fastapi import APIRouter, HTTPException
from restart_api.deps import study_loader
from restart_api.schemas import OptimizationDetailDTO, OptimizationSummaryDTO

router = APIRouter(tags=["optimizations"])

@router.get("/optimizations", response_model=list[OptimizationSummaryDTO])
def list_optimizations() -> list[OptimizationSummaryDTO]:
    return study_loader().list_summaries()

@router.get("/optimizations/{study_id}", response_model=OptimizationDetailDTO)
def get_optimization(study_id: str) -> OptimizationDetailDTO:
    try:
        return study_loader().get_detail(study_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"study not found: {study_id}") from exc
```
- `routers/v1/__init__.py`: import `optimizations`, `router.include_router(optimizations.router)`.

- [ ] **Step 1 — failing test** (endpoint contract, mirror `test_teams.py` client setup):
```python
from fastapi.testclient import TestClient
from restart_api.main import create_app
from restart_api.settings import Settings

def _client():
    return TestClient(create_app(Settings(app_env="test")))

def test_list_optimizations_endpoint():
    r = _client().get("/api/v1/optimizations")
    assert r.status_code == 200
    body = r.json()
    assert any(s["id"] == "england-vs-argentina" for s in body)

def test_get_optimization_detail_endpoint():
    r = _client().get("/api/v1/optimizations/england-vs-argentina")
    assert r.status_code == 200
    d = r.json()
    assert d["convergence_tpe"] and d["axes"] and d["insights"]

def test_get_optimization_404():
    assert _client().get("/api/v1/optimizations/nope").status_code == 404
```
- [ ] **Step 2 — run, expect fail** (404 on list / route missing).
- [ ] **Step 3 — implement** deps + router + wiring.
- [ ] **Step 4 — run, expect pass:** `uv run pytest apps/backend/tests/test_optimizations.py -q`.
- [ ] **Step 5 — commit:** `feat(api): read-only /optimizations endpoints`

### Task 1.5: `restart_opt`-not-imported guard

**Files:** Test `test_optimizations.py`

- [ ] **Step 1 — failing test:**
```python
import sys
def test_runtime_never_imports_restart_opt():
    # Importing the app must not drag the optimizer (Optuna/LightGBM/SHAP) in.
    for m in [k for k in sys.modules if k.startswith("restart_opt")]:
        del sys.modules[m]
    import importlib
    importlib.import_module("restart_api.main")
    assert not any(k == "restart_opt" or k.startswith("restart_opt.") for k in sys.modules)
```
- [ ] **Step 2 — run** (expect pass if clean; if fail, remove the offending import).
- [ ] **Step 3 — commit if changed:** `test(api): assert optimizer never enters API runtime`

### Task 1.6: OpenAPI + shared-types drift

- [ ] **Step 1 — regen:** `uv run python apps/backend/scripts/dump_openapi.py; npm run gen -w "@restart/shared-types"`
- [ ] **Step 2 — verify gate:** `pwsh scripts/verify.ps1` → green.
- [ ] **Step 3 — commit:** `chore(api): regenerate OpenAPI + shared-types for optimization surface`

**M1 done → STOP, confirm green.**

---

## Milestone 2 — pitch-kit optimization SVG primitives

Mirror existing hand-rolled chart style in `packages/pitch-kit/src/charts/Histogram.tsx` (viewBox,
token CSS vars, mono numerals, no chart lib). One vitest per component asserting it renders the
expected SVG element counts and handles empty input.

### Task 2.1: `ConvergencePlot`
**Props:** `{ tpe: ConvergencePoint[]; random: ConvergencePoint[]; baseline: {mean: number; ci: [number,number]}; winnerCi?: [number,number]; width?; height? }`
- Two step-lines (TPE, random) + baseline horizontal reference + winner CI shaded band (`<rect>`).
- [ ] Test: renders 2 `polyline`, a baseline `line`, and a band `rect`; empty series → no crash.
- [ ] Implement, run vitest, commit `feat(pitch-kit): ConvergencePlot`.

### Task 2.2: `ParallelCoordinates`
**Props:** `{ trials: {params: Record<string, number|string>; value: number}[]; axes: Axis[]; width?; height? }`
- One `polyline` per trial; continuous axis → normalize `(v-min)/(max-min)`; categorical → index/(n-1)
  by `categories` order; stroke opacity/hue by `value` (color-blind-safe sequential); axes ordered as
  given (importance desc). Hover highlights a trial (state). Reduced-motion: no transition.
- [ ] Test: N trials → N `polyline`; normalization helper `normAxis(axis, value)` unit-tested at
  domain ends (→0 and →1) and a categorical midpoint.
- [ ] Implement, run vitest, commit `feat(pitch-kit): ParallelCoordinates (the search-space view)`.

### Task 2.3: `TopKTable`
**Props:** `{ rows: ConfirmRow[]; baseline: {mean:number; ci:[number,number]}; flags?: {boundary:string[]; faceValidity:string[]} }`
- Table; CI whiskers as small inline SVG; a "beats baseline" marker per row only when row `ci_lo >`
  baseline `ci_hi`; flag chips for bound-pinning / face-validity.
- [ ] Test: a row with non-overlapping CI shows the beats marker; an overlapping one does not.
- [ ] Implement, run vitest, commit `feat(pitch-kit): TopKTable vs baseline`.

### Task 2.4: exports + gate
- [ ] Add the three to `index.ts` (+ their prop types). `pwsh scripts/verify.ps1` green. Commit
  `feat(pitch-kit): export optimization primitives`.

**M2 done → STOP, confirm green.**

---

## Milestone 3 — `/optimize` + `/optimize/:id` pages  *(REVIEW CHECKPOINT)*

### Task 3.1: api.ts client
- [ ] Add to `api` object:
```ts
optimizations: () => get<OptimizationSummary[]>("/api/v1/optimizations"),
optimization: (id: string) => get<OptimizationDetail>(`/api/v1/optimizations/${id}`),
```
  (import the generated types). Commit `feat(frontend): optimization API client`.

### Task 3.2: `/optimize` library page
- [ ] `app/optimize/page.tsx` — fetch summaries, render cards (matchup, `winner_mean_xg ± ci` in
  mono, `n_trials`, engine version, stale flag). **Beats-baseline badge only when `beats_baseline`.**
  Determinism chrome consistent with `/scenarios`.
- [ ] Test (vitest + RTL): a stale study shows the stale flag; a non-beating study shows no badge.
- [ ] Commit `feat(frontend): /optimize study library`.

### Task 3.3: `/optimize/:id` detail
- [ ] `app/optimize/[id]/page.tsx` + `components/optimize/StudyDetail.tsx` composing
  `ConvergencePlot`, `ParallelCoordinates`, `TopKTable`, `InsightsPanel`, `SensitivityBanner`.
- [ ] `InsightsPanel.tsx` — render `insights[]` plain-language strings; "How?" link →
  `/docs` or `docs/09-optimization-methodology.md`.
- [ ] `SensitivityBanner.tsx` — when `sensitivity.rankings_flip`, show "Reporting routine *classes*,
  not player-precise prescriptions" (R9 honesty).
- [ ] Tests: `rankings_flip=true` renders the classes banner; `false` does not.
- [ ] `next build` green. Commit `feat(frontend): /optimize/:id study detail`.

**M3 done → STOP for REVIEW.**

---

## Milestone 4 — Workbench compare mode  *(REVIEW CHECKPOINT)*

### Task 4.0 (gate): confirm `xg_samples` present
- [ ] Assert `SimRunStatus.result` exposes per-sim `xg_samples` (check generated types /
  `GET /sim-runs/{id}`). If absent, add a backend task to surface it before the UI. Do not build the
  UI on an assumption.

### Task 4.1: `compareStats` pure fn (stats-policy core)
**Files:** Create `lib/compareStats.ts` + `.test.ts`
```ts
export interface CompareResult {
  meanDiff: number;        // mean(a_i - b_i)
  ciLo: number; ciHi: number;  // large-sample 95% CI on the mean paired difference
  significant: boolean;    // CI excludes 0
  n: number;
}
export function compareStats(a: number[], b: number[]): CompareResult
```
- Paired: require `a.length === b.length` (same seed+n) else throw. `d_i = a_i - b_i`;
  `mean ± 1.96 * sd(d)/sqrt(n)`; `significant = ciLo > 0 || ciHi < 0`.
- [ ] **Failing tests:**
```ts
it("flags a real difference as significant", () => {
  const a = Array(200).fill(0.10), b = Array(200).fill(0.02);
  const r = compareStats(a, b);
  expect(r.meanDiff).toBeCloseTo(0.08); expect(r.significant).toBe(true);
});
it("does not flag noise as significant", () => {
  const a = [0.1, 0.0, 0.2, 0.0], b = [0.0, 0.1, 0.0, 0.2];
  expect(compareStats(a, b).significant).toBe(false);
});
it("throws on unpaired lengths (CRN requires same seed+n)", () => {
  expect(() => compareStats([0.1], [0.1, 0.2])).toThrow();
});
```
- [ ] Implement, run vitest (`npm run test -w @restart/frontend`), commit
  `feat(frontend): compareStats paired-difference CI (CRN)`.

### Task 4.2: compare UI
- [ ] In the workbench Simulate surface: pick scenario B; run both via `api.createSimRun` at the
  **same `seed` + `n_sims`** (UI disables compare if they differ). Fetch both `xg_samples`, call
  `compareStats`. Overlay two `Histogram`s on a **shared x-domain**. Winner badge **only if**
  `result.significant`; else "No significant difference (CIs overlap)".
- [ ] Test: equal inputs → no badge; clearly-separated inputs → badge + correct sign.
- [ ] `next build` green. Commit `feat(frontend): workbench CRN compare mode`.

**M4 done → STOP for REVIEW.**

---

## Milestone 5 — 3D replay (R3F, dynamic-imported)

### Task 5.1: deps
- [ ] `npm i -w @restart/frontend @react-three/fiber three && npm i -D -w @restart/frontend @types/three`.
  Commit `chore(frontend): add R3F + three (3D replay only)`.

### Task 5.2: `Replay3D`
**Consumes the same `SimulateResponse`.** `ball_path (samples,3)` → `Line`/mesh arc;
`att_tracks/def_tracks (T,n,2)` → ground-plane (`z=0`) markers stepped by `track_times_s`. Camera
presets: broadcast (angled high), behind-goal (−x looking +x), GK (on goal line). Reduced-motion →
static framed view, no auto-orbit.
- [ ] Build `Replay3D.tsx` in pitch-kit, exported via a **separate** entry (not pulled by the 2D
  barrel) so the app can `dynamic(() => import(...), { ssr: false })`.
- [ ] Smoke test: component module imports without a WebGL context (guard render in test).
- [ ] Commit `feat(pitch-kit): Replay3D over the shared replay JSON`.

### Task 5.3: toggle + isolation
- [ ] `ReplayPanel.tsx`: `2D⇄3D` toggle; 3D via `next/dynamic` (`ssr:false`, loading fallback);
  2D remains default + SVG fallback.
- [ ] Verify R3F/three absent from the default chunk (inspect `next build` output / dynamic chunk).
- [ ] `pwsh scripts/verify.ps1` green. Commit `feat(frontend): on-demand 3D replay toggle`.

**M5 done → STOP, confirm green.**

---

## Milestone 6 — Docs, ADR-008, handoff + PR

- [ ] `docs/adr/ADR-008-optimization-surface-and-3d-replay.md` — decisions: data-only study boundary
  (extends ADR-006); CRN compare pairing via `sim_seeds` contract + no-winner-without-significance;
  3D over existing replay JSON (`ball_path` z, players ground-plane), R3F dynamic-imported; charts
  still hand-rolled SVG (visx React-18-capped); `/teams` deferred to Phase 7.x. Add to
  `docs/adr/README.md` index.
- [ ] `TECHNICAL_DEBT.md` — close 🟡 "No 3D visualization"; note `/teams` deferred.
- [ ] `PROJECT_STATUS.md`, `CHANGELOG.md`, `apps/frontend/README.md`, `docs/07-ui-ux-design.md`
  (mark `/optimize`, compare, 3D shipped). Rewrite `PHASE_HANDOFF.md` ("Last completed: Phase 7";
  "Next: Phase 7.x team-intelligence / engine calibration").
- [ ] `pwsh scripts/verify.ps1` green. Commit `docs(phase7): ADR-008 + handoff/status/changelog`.
- [ ] PR → `main`: `gh pr create --base main --title "Phase 7 — Optimization UI & 3D replay"`.

---

## Self-Review (coverage vs spec)
- Read-only study API (§4 M1) → Tasks 1.1–1.6 ✓ (data-only boundary asserted in 1.5).
- pitch-kit primitives (M2) → 2.1–2.4 ✓ (hand-rolled SVG, no visx).
- /optimize pages + SHAP insights + sensitivity honesty (M3) → 3.1–3.3 ✓.
- Compare CRN + no-badge-without-significance (M4) → 4.0–4.2 ✓ (pure fn = policy enforcement).
- 3D over same JSON, dynamic import (M5) → 5.1–5.3 ✓.
- ADR-008 + docs + PR (M6) ✓. `/teams` explicitly deferred ✓.
- Constraints: ENGINE_VERSION unchanged, determinism, no scraped ratings, deps frontend-only,
  verify gate each milestone — all stated ✓.

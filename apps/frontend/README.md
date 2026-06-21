# Restart Lab — Frontend

Next.js 16 (App Router, Turbopack) · React 19 · TypeScript strict · Tailwind v4.
The product surface is the **Scenario Workbench** (design doc 07): one stateful
page, three modes — Build · Simulate · Replay.

## Run

```bash
# from the repo root
uv run uvicorn restart_api.main:app --app-dir apps/backend/src   # API on :8000
npm run dev -w @restart/frontend                                 # app on :3000
```

Env (optional):

- `NEXT_PUBLIC_API_BASE_URL` — API base (default `http://localhost:8000`).
- `NEXT_PUBLIC_API_KEY` — sent as `X-API-Key` on writes when the API configures a key
  (demo deployments leave both unset).

## Architecture

```
src/
  app/
    page.tsx                 landing
    scenarios/page.tsx       library: canonical seed + saved scenarios (empty state teaches)
    scenarios/[id]/page.tsx  workbench host (client) -> ScenarioWorkbench
    optimize/page.tsx        study library (beats-baseline badge only when significant)
    optimize/[id]/page.tsx   study detail -> StudyDetail (convergence, parallel-coords, top-k, SHAP)
  components/workbench/
    ScenarioWorkbench.tsx    owns mode + B/S/R/C keys; loads scenario + real squads
    BuildPanel.tsx           real-squad + routine/scheme pickers; snap-to-grid planning overlay
    SimulatePanel.tsx        launch sim-run, poll progress, render distributions + KPI/CI cards
    ReplayPanel.tsx          2D ReplayPlayer + on-demand 3D toggle; worst/median/best picker
    ComparePanel.tsx         two scenarios, common-random-number paired-difference CI
    Replay3D.tsx             R3F 3D replay (dynamic-imported, ssr:false); camera presets
    replay3d-util.ts         pure world->scene + camera-preset math (tested without WebGL)
    DeterminismBanner.tsx    `engine <v> · seed N · n=…` (mono)
  components/optimize/       StudyDetail, InsightsPanel, SensitivityBanner
  lib/api.ts                 typed client + pollSimRun (polling, not SSE)
  lib/compareStats.ts        paired-difference CI (CRN); winner only when CI excludes 0
```

Shared workspace packages (source-shipped, transpiled in place):

- **`@restart/pitch-kit`** — the canonical 105×68 SVG `Pitch`, the `ReplayPlayer`
  (scrubber, event markers, space=play/pause, ←/→ scrub, honors
  `prefers-reduced-motion`), and hand-rolled SVG charts (`Histogram` with an
  optional shared-`domain` for compare mode, `Ecdf`, `KpiCard` with a CI whisker +
  "how?" popover, and the optimization primitives `ConvergencePlot` /
  `ParallelCoordinates` / `TopKTable`). `tokens.css` holds the full design scale;
  `globals.css` imports it. Charts are plain SVG, not visx
  ([ADR-007 d7](../../docs/adr/ADR-007-api-workbench-and-persistence.md): visx peers cap at React 18).
  3D replay is the one exception (R3F), dynamic-imported in the frontend so three.js
  never enters the default bundle ([ADR-008](../../docs/adr/ADR-008-optimization-surface-and-3d-replay.md)).
- **`@restart/shared-types`** — API DTOs generated from `openapi.json`.

## Conventions surfaced in the UI (doc 07)

- **Determinism is visible:** every result panel shows engine/seed/n in mono.
- **Honest uncertainty:** every probability carries its CI; the compare mode (`C`)
  shows a winner only when the common-random-number paired-difference CI excludes
  zero, and `/optimize` only badges "beats baseline" on non-overlapping CIs.
- **Empty states teach:** a new scenario opens on the canonical WC2026 corner.
- **Scenarios are immutable** named specs; Build forks a new one (no update endpoint).
- The Build planning handles (delivery target / runner zone) are a **local
  annotation** with live kinematic feasibility — the engine simulates the
  *selected routine* (the spec is ids only by design), not free-form geometry.

## Tests

```bash
npm run test -w @restart/frontend        # Vitest (unit/component)
npm run test:e2e -w @restart/frontend    # Playwright journey (boots both servers)
```

The E2E runs the 3-minute journey at a reduced deterministic budget (`n_sims=24`,
ADR-007 throughput reality) over the identical build → run → distributions →
replay path. It needs the committed marts present (same precondition as the
backend's data-dependent tests).

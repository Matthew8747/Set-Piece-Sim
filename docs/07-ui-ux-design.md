# UI/UX Design Plan — Restart Lab

**Version:** 0.1 · **Status:** Design review draft

---

## 1. Design positioning

Target register: **elite football operations software** — the tool on the analyst's laptop in
the team hotel, not a developer portfolio page. Reference points for tone (not for copying):
StatsBomb IQ's data density, SkillCorner's motion clarity, broadcast tactical graphics'
immediate legibility.

**Anti-goals (the "generic developer portfolio" failure modes, named so we can test against
them):** purple-gradient hero sections; emoji-led feature cards; lorem-ipsum-shaped marketing
copy; default-styled Plotly/Bootstrap panels; dark mode as decoration rather than information
design.

### Design language

| Token | Decision |
|---|---|
| Foundation | Dark UI: near-black green-tinted neutrals (`#0B0F0D` family) — dark because the pitch is the hero surface and saturated trajectory/heat colors need a quiet ground |
| Accents | Pitch-line off-white for chrome; one signal green (`#00E07B` family) for attacking/positive; one amber for defensive/risk; team identity colors used *only* on pitch entities, never on chrome |
| Type | Inter (UI) + IBM Plex Mono (all numerals: KPIs, coordinates, seeds) — tabular numerals everywhere data aligns |
| Numbers | Every probability with its CI (`2.4% ±0.3`); every model number gets a "how?" affordance (popover → method + model card link) |
| Pitch rendering | One canonical SVG pitch component (105×68 m truth, correct penalty-area geometry) shared by builder, replay, heatmaps — built once in `packages/pitch-kit`, used everywhere |
| Motion | Replay easing = simulation kinematics (no decorative tweening); UI transitions ≤ 150 ms; zero scroll-triggered animation |

## 2. Information architecture

```
/                     Landing: one paragraph, one live replay loop, one CTA ("Open a scenario")
/scenarios            Library: canonical WC2026 scenarios + user scenarios
/scenarios/:id        SCENARIO WORKBENCH (the core surface, three modes):
                        Build   — pitch editor: drag players, draw runs, set delivery, pick scheme
                        Simulate— run batches; distributions, KPIs+CIs, heatmaps, quarantine info
                        Replay  — 2D match-style replay w/ trajectory trails, contest markers,
                                  scrubber; sample picker (median/best/worst/random)
/optimize             Studies: convergence, parallel-coords of trials, top-k vs baseline
/optimize/:id         Study detail + surrogate SHAP "insights" panel (plain-language findings)
/teams                Team Intelligence: squad aerial/pace profiles, mismatch matrix vs opponent
/teams/compare        Nation vs nation: corner-threat & corner-defense report cards
/reports/:id          Exportable report (print-CSS A4 / PDF): the artifact an analyst would
                        hand a head coach
/models               Model registry: cards, calibration plots, assumption registry
/docs                 Methods: how the sim works (public-facing simulation assumptions)
```

The Scenario Workbench (Build → Simulate → Replay as one stateful surface, not three pages) is
the product. The 3-minute reviewer journey (PRD §6) lives entirely here.

## 3. Key components & visualization choices

| Component | Approach | Notes |
|---|---|---|
| Pitch editor | SVG + pointer events (no drag lib) | Snap-to-grid 0.5 m; run paths as draggable polylines w/ timing handles; kinematic feasibility shown live (run that the player can't make in time renders red) |
| 2D replay | Canvas layer over SVG pitch | 60 fps for 23 dots + ball + trails; scrubber with event markers (kick/contact/shot); SVG-only fallback acceptable at this entity count if Canvas costs schedule |
| Outcome distributions | visx: histogram + ECDF of xG; KPI cards with CI whiskers | Compare mode overlays two scenarios with common-random-number difference CI |
| Heatmaps | First-contact & shot-origin hexbins on pitch | Shared color scale across compared scenarios (classic deception trap avoided) |
| Optimization views | visx: convergence (best-so-far ± CI band), parallel coordinates, top-k table | Parallel-coords is the "wow" view of the search space |
| Mismatch matrix | Sortable table + small-multiple bars | Height/jump-reach and pace deltas, attacker × defender |
| 3D replay (Tier 2) | React Three Fiber; camera presets (broadcast / behind-goal / GK view) | Consumes the same replay JSON as 2D — format designed for both from day one |
| Reports | Server-rendered page + print CSS | PDF via headless print; no client PDF lib |

## 4. UX details that signal "real product"

- **Empty states teach:** a new scenario opens pre-loaded with a sensible routine vs zonal
  defense, not a blank pitch.
- **Progressive disclosure:** coach persona sees KPIs and replays; analyst expands CIs,
  quarantine counts, seeds; data scientist follows links to model cards and raw artifacts.
- **Determinism surfaced:** every result panel shows `engine v0.4.1 · seed 1837 · n=10,000` in
  mono — reproducibility as visible craft.
- **Honest uncertainty:** CIs by default; comparisons refuse a winner badge without
  significance (UI enforces the stats policy from Simulation Architecture §5.4).
- **Keyboard:** space = play/pause, ←/→ = scrub, B/S/R = workbench modes.

## 5. Accessibility & performance

- WCAG AA contrast on the dark theme (verified per token, not vibes); color-blind-safe
  trajectory/heat palettes (team colors get shape redundancy: solid vs hollow markers).
- Replay honors `prefers-reduced-motion` (step mode).
- Bundle discipline: R3F (Tier 2) loaded only on demand via dynamic import; visx tree-shakes;
  Lighthouse ≥ 90 perf on report pages (SSR'd, near-static).

## 6. Alternatives considered

| Decision | Alternative | Why rejected |
|---|---|---|
| Custom SVG/Canvas pitch | Plotly/ECharts pitch hacks | Styling ceiling reads "dashboard template," not "operations platform"; pitch interactions are the product |
| visx | D3 direct | D3 owns the DOM, React owns the DOM — pick one owner; visx = D3 math with React rendering |
| Dark operations theme | Light editorial theme | Defensible either way; dark chosen for pitch-as-hero and data-color separation **(reversible — pure token swap if review disagrees)** |
| Workbench (one surface, three modes) | Separate builder/results/replay pages | State continuity is the demo: tweak → re-run → compare without navigation |

# Phase 8 — Scenario Realism — Design

**Status:** Approved · **Engine:** `sim/0.4.0` → **`sim/0.5.0`** (first engine change since P4) ·
**Branch:** `feat/phase8-scenario-realism` (off `main` @ `dd29ce4`; independent of P7/PR #7)

## 1. Goal

Make the searched scenario space look and play like a real set-piece. Review feedback: replays show
~5 attackers vs an always-11 defence, and too little routine variance. Root cause (verified):
`compile_scenario` instantiates **only the routine's runners + kicker** as attackers
(`compile.py:313-317`), while `DefensiveScheme` always accounts for **10 outfield + GK = 11**
(`scheme.py` invariant). The genome (`CornerGenome`, `n_runners=4`, box-only `ZONE_GRID`) is the
narrow part — the engine and the hand-built library already support richer routines (e.g.
`edge_of_box_pullback`, `decoy_overload`, `direct_free_kick`).

## 2. Boundary (what this phase is and is NOT)

- **Pure-core only:** changes live in `restart.optimize` (genome) and `restart.tactics` (scheme
  library). No web/DB/ML/IO in the core (the dependency rule holds).
- **Bumps `ENGINE_VERSION`** (`sim/0.4.0` → `sim/0.5.0`): more attackers placed in a scenario changes
  simulated outcomes for the same routine, so the engine build identifier must change. The committed
  canonical `study.json` is re-baselined.
- **NOT in scope:** evolutionary search (GA/CMA-ES) + lineage viz — a later optimizer phase, and
  gated on the 🔴 Numba kernel for budget. Offside lines + runners-from-off-the-ball + multi-touch —
  stays O-3 (carried debt). Engine `[knob]` calibration (🔴) — untouched. Variable-arity search —
  excluded (O-2 registered assumption).

## 3. Decisions (from brainstorming)

- **More attackers via more runners + off-ball zones** (not a new role taxonomy). All attackers are
  runners; off-ball behaviour comes from off-ball target zones + existing intents
  (`decoy`/`screen`/`second_ball`).
- **Fixed arity per study, raised to ~7 attackers** (kicker + 6 runners). Honors O-2 (no
  variable-arity search); keeps CRN pairing + SHAP clean.
- **Basic free-kick genome now**, using the engine's existing FK scaffolding (`fk_position`,
  `wall_size`, `set_piece` code 1). Offside/off-ball runners explicitly deferred to O-3.

## 4. Components

### 4.1 Off-ball zones + wider corner template (`restart/optimize/genome.py`)
- Extend `ZONE_GRID` with off-ball, football-plausible zones (all within the attacking third, valid
  `PitchPoint`s): `top_of_box` (≈x35,y0), `left_half_space` (≈x41,y-10), `right_half_space`
  (≈x41,y10), `deep_recycle` (≈x32,y0). `edge` retained.
- Extend `_DEFAULT_STARTS` to 7 entries; `_DEFAULT_ZONES`/`_DEFAULT_INTENTS`/`_DEFAULT_DELAYS` to 7,
  with the new slots defaulting to off-ball intents at off-ball zones.
- `CornerGenome.n_runners` cap rises with `_DEFAULT_STARTS` (now 7); the **canonical study uses
  `n_runners=6`**. `to_scenario` already raises if the attacking team lacks enough outfielders — keep
  that guard.

### 4.2 Free-kick genome (`restart/optimize/genome.py`, new `FreeKickGenome`)
- Builds a `FREE_KICK` `RoutineSpec` from the same per-runner template (zones/delays/intents) +
  delivery (target/speed/spin/type). `fk_position` is carried on the **base `Scenario`** (study
  config), not searched — `to_scenario` preserves `base.fk_position` and sets
  `set_piece=FREE_KICK`. Wall is the defensive scheme's concern (`wall_size>0`), already compiled.
- Validation reuse: `Scenario` already requires `fk_position` for FK and `wall_size==0` only for
  corners — no new rules. Offside/off-ball timing: **not modeled** (documented O-3 deferral).

### 4.3 Structured defensive defaults (`restart/tactics/library.py`)
- Add one structured **`near_post_man`** `DefensiveScheme`: a near-post zonal anchor + a near-post
  man-marker + a flat line, summing to the =10 invariant. Add it to `all_schemes()`.
- Point the canonical corner study at a near-post-covering scheme (today's `zonal_six_two` already
  has near-post inner/outer guards — confirm/keep). No change to the scheme model or compile logic.

### 4.4 Engine version + re-baseline (`restart/__init__.py`, `optimization_studies/`)
- `ENGINE_VERSION = "sim/0.5.0"`.
- Re-run `restart-opt canonical` offline at the committed scoped budget → regenerate
  `optimization_studies/england-vs-argentina/study.json` (now a 7-attacker genome → more axes,
  `engine_version: sim/0.5.0`). Commit the regenerated artifact.

## 5. Data flow (unchanged shape)

`genome.to_scenario(base, params)` → `Scenario` → `compile_scenario` → `SimProgram` (now `na=7`) →
engine → xG. The optimizer driver (`restart_opt`) consumes the wider `SearchSpace` unchanged. The
persisted `study.json` keeps its schema (more trial-param keys); the P7 read-only surface renders the
extra parallel-coords axes automatically and shows the study as current once both branches merge.

## 6. Testing (TDD)

- **Genome:** new zones validate to in-bounds `PitchPoint`s; `CornerGenome(n_runners=6)` builds a
  valid 6-assignment `Scenario`; `n_runners=7` allowed, `8` raises; `FreeKickGenome.to_scenario`
  builds a `FREE_KICK` (fk_position preserved, runners present) and raises without `fk_position`.
- **Scheme:** `near_post_man()` satisfies the =10 invariant and covers the near post; it is in
  `all_schemes()`.
- **Compile/engine:** a 6-runner corner compiles to `n_attackers=7`; the FK path compiles with a wall.
- **Determinism:** same `Scenario` ⇒ identical `SimProgram` bytes (existing property extended to the
  new template).
- **Re-baseline fallout (expected):** tests pinning canonical xG / SimProgram values or
  `ENGINE_VERSION == "sim/0.4.0"` are updated to `sim/0.5.0` and the new template — gated by the
  version bump, not silent drift.

## 7. Ripple & risks

- **Frontend/API:** none required. `att_tracks` render dynamically (7 attackers just appear);
  parallel-coords gains axes; OpenAPI/shared-types unaffected (study.json shape stable).
- **Risk — re-baseline invalidates pinned tests:** expected and intended; update them in the same
  commit as the version bump so the gate stays green.
- **Risk — throughput:** 7 attackers + wider space = more compute at ~3 sims/s; keep the scoped
  study budget (the 🔴 kernel is still owed; do not widen the budget here).
- **Risk — FK scope creep:** keep the FK genome to delivery + runners + wall; offside/off-ball is a
  hard O-3 line not crossed in this phase.

## 8. Milestones

- **M1 — Off-ball zones + 7-attacker corner template** (`genome.py`): zones, starts/defaults, cap,
  tests. No version bump yet (additive; default canonical still 4 until M4 flips it).
- **M2 — `near_post_man` scheme** (`library.py`): structured default + tests.
- **M3 — `FreeKickGenome`** (`genome.py`): FK builder + tests.
- **M4 — ENGINE_VERSION bump + re-baseline**: `sim/0.5.0`, canonical study `n_runners=6`, re-run
  `restart-opt canonical`, update pinned tests, regenerate `study.json`. Full `verify.ps1` green.
- **M5 — Docs + ADR-009 + handoff + PR** against `main`.

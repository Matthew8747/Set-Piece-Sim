# Phase 8 - Scenario Realism - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline) or
> subagent-driven-development. Steps use checkbox (`- [ ]`) tracking.

**Goal:** Widen the searched scenario space to look/play like a real set-piece - 7 attackers with
off-ball roles, a basic free-kick genome, structured defensive defaults - and bump `ENGINE_VERSION`.

**Architecture:** Pure-core only (`restart.optimize.genome`, `restart.tactics.library`). No web/ML/IO.
Engine semantics change (more attackers placed) → `sim/0.4.0` → `sim/0.5.0`; canonical `study.json`
re-baselined. GA/evolution + offside/off-ball deferred (later phases).

**Tech Stack:** Python 3.12, pydantic domain models, numpy SoA compile, pytest, `restart-opt` CLON CLI.

**Verify gate (each milestone):** run the steps in `scripts/verify.ps1` (ruff, black, mypy, pytest;
JS gates unaffected). Spec: `docs/superpowers/specs/2026-06-20-phase8-scenario-realism-design.md`.

---

## File Structure
- Modify `packages/simulation-core/src/restart/optimize/genome.py` - off-ball zones, 7-slot template,
  `FreeKickGenome`.
- Modify `packages/simulation-core/src/restart/tactics/library.py` - `near_post_man()` scheme.
- Modify `packages/simulation-core/src/restart/__init__.py` - `ENGINE_VERSION`.
- Modify `packages/optimizer/src/restart_opt/canonical.py` - `CornerGenome(n_runners=6)`.
- Tests: `packages/simulation-core/tests/test_optimize_genome.py`,
  `packages/simulation-core/tests/test_tactics_*` (scheme), plus any pinned-value tests to re-baseline.
- Re-baseline artifact: `optimization_studies/england-vs-argentina/study.json`.

---

## M1 - Off-ball zones + 7-attacker corner template

### Task 1.1: Off-ball zones in `ZONE_GRID`
- [ ] **Failing test** (`test_optimize_genome.py`):
```python
def test_zone_grid_has_off_ball_zones_all_on_pitch():
    from restart.optimize.genome import ZONE_GRID
    for name in ("top_of_box", "left_half_space", "right_half_space", "deep_recycle"):
        assert name in ZONE_GRID  # off-ball options exist
        ZONE_GRID[name]  # constructs a valid (on-pitch) PitchPoint or raises
```
- [ ] **Run** → fail (KeyError). `uv run pytest packages/simulation-core/tests/test_optimize_genome.py -q`
- [ ] **Implement:** add to `ZONE_GRID` (all valid `PitchPoint`s, attacking third):
```python
    "top_of_box": PitchPoint(x=35.0, y=0.0),
    "left_half_space": PitchPoint(x=41.0, y=-10.0),
    "right_half_space": PitchPoint(x=41.0, y=10.0),
    "deep_recycle": PitchPoint(x=32.0, y=0.0),
```
- [ ] **Run** → pass. **Commit** `feat(optimize): off-ball target zones in the corner genome`.

### Task 1.2: 7-slot runner template
- [ ] **Failing test:**
```python
def test_corner_genome_supports_seven_attackers():
    g = CornerGenome(n_runners=6)  # kicker + 6 = 7 attackers
    sc = g.to_scenario(base_scenario(), g.defaults())
    assert len(sc.routine.assignments) == 6
    with pytest.raises(ValueError):
        CornerGenome(n_runners=8)  # beyond the template
```
- [ ] **Run** → fail (cap is 6 today → n_runners=6 ok but template has only 6 starts; ensure 7).
  Actually extend the template first.
- [ ] **Implement:** extend `_DEFAULT_STARTS` to 7 plausible starts; extend `_DEFAULT_ZONES`,
  `_DEFAULT_INTENTS`, `_DEFAULT_DELAYS` to 7 entries (new slots off-ball, e.g.
  `("...","top_of_box","left_half_space")`, intents `("...","decoy","second_ball")`). The
  `__post_init__` cap follows `len(_DEFAULT_STARTS)` automatically.
- [ ] **Run** → pass. **Commit** `feat(optimize): widen corner template to 7 attackers`.

### Task 1.3: defaults validity
- [ ] **Failing/confirming test:** `CornerGenome(n_runners=6).to_scenario(base_scenario(), defaults())`
  compiles: `compile_scenario(sc).n_attackers == 6`.
- [ ] **Run** → pass (if template consistent). **Commit** if changed.

**M1 done → ruff/black/mypy/pytest (core) green.**

---

## M2 - `near_post_man` defensive scheme

### Task 2.1
- [ ] **Failing test** (`test_tactics_library.py` or the scheme test file):
```python
def test_near_post_man_scheme_valid_and_covers_near_post():
    from restart.tactics.library import near_post_man, all_schemes
    s = near_post_man()
    assert len(s.zonal_points) + s.n_man_markers + s.wall_size == 10
    assert any(p.x >= 50 and p.y < 0 for p in s.zonal_points)  # a near-post anchor
    assert s in all_schemes()
```
- [ ] **Run** → fail. **Implement** `near_post_man()` (near-post zonal anchor + near-post man-marker +
  flat line summing to 10) and add to `all_schemes()`.
- [ ] **Run** → pass. **Commit** `feat(tactics): structured near_post_man defensive scheme`.

---

## M3 - Free-kick genome

### Task 3.1
- [ ] **Failing test:**
```python
def test_free_kick_genome_builds_free_kick_scenario():
    from restart.optimize.genome import FreeKickGenome
    from restart.tactics.routine import SetPiece, PitchPoint
    base = base_scenario().model_copy(update={"fk_position": PitchPoint(x=35.0, y=-20.0)})
    g = FreeKickGenome(n_runners=4)
    sc = g.to_scenario(base, g.defaults())
    assert sc.routine.set_piece == SetPiece.FREE_KICK
    assert sc.fk_position is not None and len(sc.routine.assignments) == 4

def test_free_kick_genome_requires_fk_position():
    from restart.optimize.genome import FreeKickGenome
    g = FreeKickGenome()
    with pytest.raises(ValueError):
        g.to_scenario(base_scenario(), g.defaults())  # base has no fk_position
```
- [ ] **Run** → fail. **Implement** `FreeKickGenome` (mirrors `CornerGenome` builder but
  `set_piece=FREE_KICK`, preserves `base.fk_position`, delivery target validated for FK). Reuse the
  per-runner param construction; raise a clear error if `base.fk_position is None`.
- [ ] **Run** → pass. **Commit** `feat(optimize): basic free-kick genome (offside/off-ball deferred)`.

**M3 done → core gates green.**

---

## M4 - ENGINE_VERSION bump + re-baseline  *(REVIEW CHECKPOINT)*

### Task 4.1: bump + canonical config
- [ ] `restart/__init__.py`: `ENGINE_VERSION = "sim/0.5.0"`.
- [ ] `restart_opt/canonical.py`: `genome = CornerGenome(n_runners=6)`; keep `zonal_six_two()` (near
  post covered) or switch to `near_post_man()` - decide in review.
- [ ] **Re-baseline pinned tests:** grep `sim/0.4.0` and any canonical xG/SimProgram value assertions;
  update to `sim/0.5.0` and the 7-attacker template. `grep -rn "sim/0.4.0" packages apps`.
- [ ] **Run** core pytest → green.

### Task 4.2: regenerate the committed study
- [ ] Re-run the canonical study at the committed scoped budget:
  `uv run restart-opt canonical --seed 0 --trials 24 --screen 40 --confirm 400 --k 3 --sens 60`
  (match the existing `config` block in `study.json`).
- [ ] Confirm `optimization_studies/england-vs-argentina/study.json` now has `engine_version:
  sim/0.5.0` and 16+ genome params per trial (7-attacker). **Commit** study + version + canonical +
  test updates: `feat(engine)!: sim/0.5.0 - 7-attacker template, re-baseline canonical study`.

**M4 done → full `verify.ps1` green. STOP for review.**

---

## M5 - Docs, ADR-009, handoff, PR
- [ ] `docs/adr/ADR-009-scenario-realism.md` - wider template (O-2 widened, arity still fixed), basic
  FK genome (offside/off-ball = O-3 deferred), structured defence, `ENGINE_VERSION` bump rationale +
  re-baseline. Add to ADR index.
- [ ] Update `simulation-assumptions` / `ASSUMPTIONS_REGISTER` (O-2 widened note), `TECHNICAL_DEBT`
  (FK partial; offside/off-ball still O-3), `PROJECT_STATUS`, `CHANGELOG`, rewrite `PHASE_HANDOFF`.
- [ ] Full `verify.ps1` green. PR → `main`: `gh pr create --base main --title "Phase 8 - Scenario realism (sim/0.5.0)"`.

---

## Self-Review (coverage vs spec)
- Off-ball zones + 7 attackers (§4.1) → M1 ✓
- `near_post_man` (§4.3) → M2 ✓
- FreeKickGenome (§4.2) → M3 ✓
- ENGINE_VERSION + re-baseline (§4.4) → M4 ✓
- Docs/ADR/PR (§8 M5) ✓
- Constraints: pure-core, fixed arity (O-2), FK offside deferred (O-3), scoped budget - all stated ✓.

# Phase Handoff

> Rewritten at the end of every completed phase.

## Last completed phase: Phase 8 — Scenario realism (engine `sim/0.5.0`)

> Phase 7 (Optimization UI & 3D replay) ships in a **parallel** branch / PR #7 off the same `main`;
> this handoff covers the engine work in `feat/phase8-scenario-realism`.

### What shipped

- **Wider corner template — 7 attackers with off-ball roles.** `restart.optimize.genome`: the
  `ZONE_GRID` gains off-ball target zones (`top_of_box`, `left_half_space`, `right_half_space`,
  `deep_recycle`) and the runner template grows to 7 slots, so the optimizer can build a realistic
  overload (box contesters + lurkers/recyclers) instead of four bodies in the six-yard box. The
  root cause it fixes: `compile_scenario` instantiates only the routine's runners + kicker as
  attackers, while a `DefensiveScheme` always accounts for 10 outfield + GK = 11 — so the old
  4-runner default rendered ~5 vs 11. Arity is **fixed per study** (assumption O-2 — no
  variable-arity search); the canonical study runs 6 runners (7 attackers, a 22-param genome).
- **Basic free-kick genome.** `FreeKickGenome` builds a `FREE_KICK` routine over the engine's
  existing FK scaffolding (`fk_position` on the `Scenario`, `wall_size` on the scheme — both already
  compiled). The corner and free-kick genomes share extracted template builders
  (`_template_params` / `_build_delivery` / `_build_assignments` / `_role_map`) so they cannot drift.
  Offside lines + off-ball runner timing are **not** modeled — carried O-3.
- **Structured defence.** A `near_post_man` `DefensiveScheme` (near-post anchor + flat line + 3
  man-markers = 10 outfield) joins the library.
- **`ENGINE_VERSION` `sim/0.4.0` → `sim/0.5.0`** ([ADR-009](../adr/ADR-009-scenario-realism.md)).
  Placing more attackers changes a routine's simulated context/results, so the engine build id bumps.
  Determinism is preserved — the same `Scenario` still compiles byte-identical (new 7-attacker + FK
  determinism tests). The committed canonical `study.json` is **re-baselined** (7-attacker, 22-param
  genome, `engine_version: sim/0.5.0`).
- **Ops:** [`scripts/rebaseline_canonical.py`](../../scripts/rebaseline_canonical.py) — an observable,
  watchdog-bounded wrapper for the long canonical re-run.
- **Docs:** ADR-009, [`docs/ROADMAP-future-enhancements.md`](../ROADMAP-future-enhancements.md)
  (the forward roadmap), updated status/debt/assumptions/changelog/methodology, and the README
  design-decisions table.

### Validation evidence

All Python gates green (ruff, black, mypy --strict, pytest). Genome: 23 tests (off-ball zones,
7-attacker + FK builders, byte-determinism). Schemes: `near_post_man` invariant + near-post coverage.
Engine version bump: the full `simulation-core` suite (441 tests) stays green; the single backend
assert pinning the version was updated to `sim/0.5.0`. The canonical study was re-baselined with the
observable wrapper (per-trial Optuna logs + 30 s heartbeat + hard watchdog) and the regenerated
`study.json` parses to `sim/0.5.0` with a 7-attacker, 22-param genome.

### Debugging history worth knowing (saves future sessions time)

1. **Never `find /` under MSYS / Git Bash.** A whole-filesystem `find` expanded across mounted
   Windows drives and hard-locked the terminal pipes during a re-baseline. Scope every search to the
   project dir; use `git status <path>` + `python -c` JSON checks for integrity, never `find`.
2. **Long offline runs need a watchdog + heartbeat.** `run_canonical` persists `study.json` only at
   the very end, so a killed mid-run leaves the committed study untouched (good) but produces nothing.
   The wrapper logs per-trial progress, a 30 s liveness heartbeat (covers the non-Optuna confirm /
   sensitivity phases), and a hard wall-clock cap (`os._exit`) so it can't hang indefinitely.
3. **MSYS path translation.** A `/tmp/...` path passed to a native Python exe via the Bash tool is
   MSYS-translated to a Windows temp path; a literal `/tmp/...` string *inside* Python is not. Read
   wrapper output via its real (cygpath-translated) path.
4. **`CornerGenome` refactor is policed by tests.** The shared template builders are covered by the
   genome + optimizer suites; any corner/FK drift fails them.

### Open decisions carried forward (NOT touched by Phase 8)

- **Throughput (🔴, now Phase 9):** the fused Numba scenario kernel — more pressing because 7
  attackers are ~2.5× slower/sim. The keystone dependency (roadmap §1).
- **Calibration (🔴):** fit the engine `[knob]`s to real base rates (goal ~5% sim vs 2–3% real) —
  roadmap §2 (simulation-based inference).
- **O-3 fidelity:** multi-touch, sequential lookahead, defender anticipation, and full free kicks
  (offside + off-ball runners) — roadmap §6.
- **Search/objective:** evolutionary + multi-objective (CVaR / robust) search and lineage viz —
  roadmap §3–4.

## Next phase: Phase 9 — Throughput (fused Numba scenario kernel)

Port the engine semantics (RK4 flight + contest resolution) into a `@guvectorize`/`njit(parallel)`
kernel over the already-flat `SimProgram` SoA arrays; police drift against the reference engine with
an equivalence test (`≤1e-9`). Target 10⁴–10⁵ sims/s to unlock the full 500/10k reference budget and
everything downstream (calibration, evolutionary/multi-objective search). See
[ADR-003](../adr/ADR-003-agent-architecture.md) d8 and [roadmap](../ROADMAP-future-enhancements.md) §1.

### Risks for Phase 9
1. **Physics drift** between the kernel and `forces.py` — contained by the `≤1e-9` equivalence test
   (the same discipline already used for the JIT physics formulas).
2. **Determinism under parallelism** — per-sim `SeedSequence`-derived seeds are scenario-independent,
   so batch order must not affect results; assert byte-identity across batch sizes.
3. **Scope** — keep it a faithful port (no semantics changes); a behaviour change would bump
   `ENGINE_VERSION` again and force another re-baseline.

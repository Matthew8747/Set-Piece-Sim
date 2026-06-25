# Phase 10 - Fused Numba scenario kernel (throughput)

**Status:** Approved (brainstorm) · **Date:** 2026-06-22 · **Branch:** `feat/phase10-throughput-kernel`
**ADR:** [ADR-011](../../adr/ADR-011-throughput-kernel.md) · **Roadmap:** §1 (the keystone) · **Engine:** `sim/0.5.0` (unchanged - faithful port, no semantics change)

## Problem

The reference engine runs at **~3 sims/s** (single trajectory ~0.4 s; the 7-attacker
template ~2.5× slower again). Every downstream ambition - bigger evolutionary populations and
more generations (so a GA can actually overtake TPE), the full 500/10k reference budget,
calibration, multi-objective - is gated on throughput. Phase 9 shipped genuine evolution but
proved the point: at the scoped budget (24 trials, population 8, ~3 generations) evolution beat
random but **TPE still won**. Throughput is what lifts it. Target **10⁴-10⁵ sims/s**.

## The constraint that shapes the whole design

The engine's RNG is `np.random.Generator(np.random.Philox(...))` (`simulation/rng.py`).
**Numba's in-kernel RNG cannot reproduce NumPy's Philox stream bit-for-bit.** The existing
`_kernels.py` flight kernel hits ≤1e-9 only because it is *deterministic* (no RNG). A full-engine
port can match the reference to ≤1e-9 **only if the kernel consumes the same draws as the
reference** - i.e. RNG must be **externalized**: drawn in NumPy host code, fed into the kernel as
arrays. This is the chosen strategy (the alternatives - in-kernel RNG with statistical-only
equivalence, or NumPy vectorize-across-sims - were considered and rejected; see ADR-011).

## Architecture

Externalized RNG makes the fast path **and** the replay path bit-identical: a kernel-found winner
replays bit-identically in the reference engine (same seed → same draws → same outcome).

```
host: draw_sim(seed, na, nd) -> SimDraws          # Philox sub-streams, fixed budget per category
  └─> kernel pass A   njit(parallel=True) prange over sims
        deterministic: delivery -> flight oracle -> agent tick (pre-kick + flight windows)
        -> interception -> contest (Gumbel) -> shot geometry + after-trajectory
        emits per sim: terminal outcome_code | SHOT_PENDING + 10-feat ShotContext row
                       + after.goal_scored + the pre-drawn scored-uniform + aim_y/aim_z + is_header
host: xG batch          LightGBM.predict over ALL shot rows  (one call)   # only non-njit step
host: pass C (vectorized)  scored = u < xg; combine with goal_scored -> GOAL/SAVED/OFF_TARGET
  -> per-sim compact output: (outcome_code, xg, is_header, fc_team)
```

LightGBM is the **only** thing outside njit and is naturally batched (GBM predict is per-row
deterministic → batched output is bit-identical to per-row → xG matches the reference to 1e-9).

### Kernel output contract (what the optimizer actually reads)

From `optimize/objective.py` + `montecarlo/aggregate.py`, the optimizer/MC consume per sim only:
`outcome_code`, `xg` (NaN if no shot), `is_header`, `first_contact_team`. **No replay tracks on the
throughput path** - `att_tracks`/`def_tracks`/trajectories stay reference-engine-only (single-sim,
on-demand, for the API 3D replay).

### The draw plan - single stream → category sub-streams

Current engine draws lazily from one Philox stream: delivery(2 normals) → jitter(na+nd uniforms) →
contest(`len(contestants)` gumbels - *variable*) → shot(2 uniforms + 2 normals + 1 scored uniform)
**or** untouched(1 uniform). The variable gumbel count blocks clean externalization.

Fix: spawn **independent sub-streams** per category from the per-sim `SeedSequence`, each with a
**fixed budget**. Over-provisioning a sub-stream is then harmless (it never shifts another category's
draws - the bug single-stream over-draw would cause).

| sub-stream | budget | draws |
|---|---|---|
| `delivery` | 2 | dir-error, speed-mult (normal) |
| `jitter` | na + nd | reaction jitter (uniform) |
| `contest` | na + nd | Gumbel per *potential* contestant; consume per actual contestant, index order |
| `shot` | 5 | aim_y, aim_z (uniform), perturb×2 (normal), scored (uniform) |
| `second_ball` | 1 | near-tie jitter (uniform) |

`SimDraws` = a frozen dataclass of these flat read-only arrays; deterministic in `(seed, na, nd)`,
scenario-independent → byte-identity across batch sizes holds (the carried hard constraint).

**This sub-stream split changes the per-sim RNG→decision mapping once** → a one-time canonical
re-baseline (model identical; aggregates move only within Monte Carlo noise; `ENGINE_VERSION` stays
`sim/0.5.0` because the *semantics* are unchanged). Accepted in the brainstorm.

### What gets ported to njit

The hot cost is the **20 ms agent tick** over ~2-4 s (≈100-200 ticks × O(na+nd)), run twice
(pre-kick + flight). Each unit is mirrored verbatim-in-semantics from its NumPy reference (the
`_kernels.py` discipline - change both together or the equivalence test catches you):

| ported unit | source today |
|---|---|
| flight RK4 + Magnus/drag/bounce | `physics/_kernels.py` (reuse as-is; already 1e-9) |
| `step_agents`, `separate` | `agents/kinematics.py` |
| `earliest_interception` | `agents/interception.py` |
| contest select + Gumbel | `engine._select_contest` / `_contest_winner` |
| delivery execution | `engine._execute_delivery` |
| shot geometry + `_shot_context` | `engine._resolve_shot` / `_shot_context` |

**Kept out of njit:** LightGBM predict (batched host call), replay-track assembly (reference-only),
pydantic/dict/string resolution (already gone after `compile_scenario`). The placeholder no-xG path
stays reference-only (the optimizer always injects an xG model).

### Module layout (pure-domain - no web/DB/ML/IO)

- `restart/engine/draws.py` - `SimDraws`, `draw_sim(seed, na, nd)`.
- `restart/engine/kernel.py` - fused pass-A njit kernel + host orchestration (pass A/B/C).
- `restart/montecarlo/runner.py` - `BatchKernelRunner` (or a `kernel=True` mode); the existing
  reference `MonteCarloRunner.run()` is **untouched** for replay/API.

## Verification gates (all green before merge)

1. **Equivalence ≤1e-9.** `tests/test_kernel_equivalence.py`: scenario matrix (corner template, FK
   genome, varied schemes) × N seeds; assert kernel `(outcome, xg, is_header, fc_team)` == reference
   engine sim-by-sim ≤1e-9 (both consume the same `SimDraws`). Plus per-sub-kernel 1e-9 tests
   (agent tick, interception, contest math) vs their NumPy refs.
2. **Determinism / byte-identity.** Kernel output for sim *i* is independent of batch size and
   ordering; `prange` parallel result == serial result bit-for-bit (the handoff parallelism risk).
3. **Throughput + honesty bar.** A bench script measures sims/s reference vs kernel on the
   7-attacker template; the gate **fails if speedup < 1000×** (target 10⁴-10⁵ sims/s). Recorded in
   docs as evidence. (Same honesty discipline as the sampler random-baseline gate: if it doesn't pay
   off, it doesn't merge.)

## Milestones (TDD, verify green each)

- **M0 - Docs.** This spec, ADR-011, the legacy/from-scratch ledger, ADR index. *(this commit)*
- **M1 - `SimDraws` + draw plan.** Implement `draws.py`; refactor the reference engine to consume
  `SimDraws` instead of calling `rng` directly. Update the engine tests to the new draw plan's golden
  values. Tests: determinism, byte-identity across batch sizes, draw-budget coverage. **Re-baseline
  trigger lands here.**
- **M2 - Port sub-kernels.** njit ports of agent tick / interception / contest / delivery / shot
  geometry, each with a ≤1e-9 equivalence test vs its NumPy reference.
- **M3 - Fused kernel + runner.** Assemble pass A/B/C and `BatchKernelRunner`. Full-pipeline ≤1e-9
  equivalence vs the reference engine; determinism / parallel byte-identity tests.
- **M4 - Throughput + wire-in.** Bench script + honesty-bar gate; wire the kernel into the optimizer
  objective path (opt-in flag). Record sims/s evidence.
- **M5 - Re-baseline canonical.** Re-run the canonical study on the kernel path with the observable
  watchdog harness (`scripts/rebaseline_canonical.py`); update `study.json` + the methodology doc.
  Verify aggregates sit within MC noise of the prior baseline; `ENGINE_VERSION` stays `sim/0.5.0`.
- **M6 - Portfolio + close-out.** Finished-or-not verdict; a scenario list for data/screenshots
  (portfolio/CV/LinkedIn); doc polish (PROJECT_STATUS, ROADMAP, CHANGELOG, PHASE_HANDOFF, legacy
  ledger); PR against `main`.

## Risks

1. **Physics/semantics drift kernel ↔ reference** - contained by the ≤1e-9 equivalence test (M1+M3).
2. **Determinism under `prange`** - per-sim `SeedSequence` sub-streams are scenario-independent;
   assert parallel==serial and batch-size invariance (M3).
3. **Draw-plan refactor churn** - M1 changes per-sim outcomes; existing engine golden tests must be
   re-pinned. Staged as its own milestone before any kernel code so the two risks don't compound.
4. **njit port surface is large** (agent tick + interception + contest). Mitigated by porting unit by
   unit with per-unit 1e-9 tests (M2) before fusing (M3).
5. **Speedup underwhelms** - the honesty bar (M4) blocks merge if it does; fall back to documenting
   the NumPy-vectorize alternative.

## Explicitly NOT in scope (deferred)

- GPU batch (JAX/CuPy) and distributed Optuna (roadmap §1.2/§1.3) - later throughput tiers.
- Engine `[knob]` calibration / SBI (roadmap §2, its own phase).
- Multi-objective Pareto + lineage viz (roadmap §4/§7) - unblocked by this phase, not part of it.
- O-3 fidelity (multi-touch / lookahead / defender anticipation / full FK).

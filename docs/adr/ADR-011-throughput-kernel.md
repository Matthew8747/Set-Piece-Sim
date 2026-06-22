# ADR-011 — Fused Numba scenario kernel with externalized RNG

**Status:** Accepted · **Date:** 2026-06-22 · **Phase:** 10
**Related:** ADR-001 (physics build-vs-buy; Numba flight kernel addendum), ADR-003 d8 (the SoA
compile boundary built *for* this kernel) + d9 (per-sim `SeedSequence` determinism), ADR-004
(`SimProgram`), ADR-006/ADR-010 (the optimizer/evolution this throughput scales), roadmap §1.
**`ENGINE_VERSION` unchanged (`sim/0.5.0`)** — a faithful port, no semantics change.

## Context

The reference engine runs at ~3 sims/s. Every downstream ambition (bigger evolutionary populations
and more generations, the full reference budget, calibration, multi-objective) is gated on
throughput (roadmap §1 — "the keystone"). The hot path was deliberately compiled to flat, read-only
SoA arrays (`SimProgram`, ADR-004 d4) precisely so a Numba kernel could run a whole batch with no
Python in the loop (ADR-003 d8). This ADR cashes that in.

The engine's RNG is `np.random.Generator(np.random.Philox(...))`. **Numba's in-kernel RNG cannot
reproduce the Philox stream bit-for-bit**, so a stochastic kernel cannot match the reference to
≤1e-9 *unless it consumes the same draws*. The existing `_kernels.py` flight kernel hits ≤1e-9 only
because it is deterministic.

## Decisions

1. **Externalize the RNG.** All per-sim Philox draws are generated in NumPy host code into a
   `SimDraws` struct; both the njit kernel and the (refactored) reference engine consume `SimDraws`
   instead of calling `rng` directly. Equivalence to ≤1e-9 then holds *by construction*, and — the
   bonus — the fast path and the single-sim replay path become bit-identical (a kernel winner
   replays exactly in the reference engine). Rejected alternatives: (a) in-kernel Numba RNG with
   *statistical-only* equivalence — lower risk but not a true drop-in and leaves a fast/replay seam;
   (b) NumPy vectorize-across-sims — keeps Philox but control-flow divergence needs heavy masking and
   tops out lower (~10³–10⁴). The exact-1e-9 externalized path was chosen for the true-drop-in
   property and the strongest equivalence story.

2. **Category sub-streams with fixed budgets.** The current single lazy stream draws a *variable*
   number of contest Gumbels (one per contestant), which blocks externalization. Instead spawn an
   independent sub-stream per draw category (`delivery`, `jitter`, `contest`, `shot`, `second_ball`)
   from the per-sim `SeedSequence`, each with a fixed budget; over-provisioning a sub-stream is
   harmless because it cannot shift another category's draws. This **changes the per-sim
   RNG→decision mapping once** → a single canonical re-baseline; the model is identical and
   aggregates move only within Monte Carlo noise, so `ENGINE_VERSION` stays `sim/0.5.0`. The
   determinism contract is preserved: sub-streams are scenario-independent and byte-identical across
   batch sizes.

3. **The kernel emits only the optimizer's output contract.** Per sim:
   `(outcome_code, xg, is_header, first_contact_team)` — exactly what `objective.py`/`aggregate.py`
   read. Replay tracks (positions over time, full trajectories) are **not** produced on the
   throughput path; they stay reference-engine-only for the on-demand API 3D replay.

4. **LightGBM stays outside njit, batched.** The kernel (pass A) runs all deterministic
   physics/agents/contest/shot-geometry and emits a `ShotContext` row for shot sims; the xG model
   scores all rows in one batched `predict` (pass B); a vectorized finalizer applies the xG Bernoulli
   with the pre-drawn uniform (pass C). GBM prediction is per-row deterministic, so batched output is
   bit-identical to the reference's per-row calls.

5. **Equivalence is enforced by test, layered.** ≤1e-9 sim-by-sim on the full pipeline (kernel vs
   reference, same `SimDraws`) and ≤1e-9 per ported sub-kernel vs its NumPy reference; byte-identity
   across batch sizes and `prange` parallel==serial; and a throughput **honesty bar** (merge blocked
   if speedup < 1000×). The reference NumPy engine remains the readable semantics oracle.

## Consequences

- Throughput rises from ~3 sims/s toward 10⁴–10⁵, unblocking real evolutionary populations/generations
  and the full reference budget — the multiplier on every later search/calibration phase.
- The optimizer objective gains an opt-in kernel path; the reference engine is unchanged for replay and
  the API (no API/OpenAPI/shared-types contract change).
- One canonical re-baseline (draw-plan change), documented; `ENGINE_VERSION` unchanged.
- `restart` stays pure-domain (the kernel imports no web/DB/ML/IO; LightGBM is injected exactly as
  today via the `XGScorer` seam, called outside the kernel).

## Explicitly NOT in scope (deferred)

- GPU batch (JAX/CuPy) and distributed Optuna studies (roadmap §1.2/§1.3) — later throughput tiers.
- Engine `[knob]` calibration / SBI (roadmap §2).
- Multi-objective Pareto + lineage visualization (roadmap §4/§7) — unblocked by this kernel, not part
  of it.

# Phase 2 Design Review & Throughput-Risk Assessment

**Date:** 2026-06-12 · **Branch:** `feat/phase2-agents-tactics` · **Status:** Approved for
implementation (ADR-003, ADR-004 accepted)

## 1. Forward-requirements review (what future phases demand of this layer)

| Future requirement | Constraint imposed on Phase 2 |
|---|---|
| Monte Carlo (P3): 10k sims < 60 s / 4 cores | Per-sim cost budget ≈ **2 ms single-core**; engine state must be flat arrays so a fused Numba kernel (ADR-001-addendum pattern) can be a port, not a rewrite |
| Large-scale scenario generation (P3/P5) | Scenario assembly out of the hot path: `compile()` once → `run(program, seed)` many; programs hashable/reusable |
| Bayesian optimization (P5) | Routine Spec fields are the genome: typed, bounded, validated; objective evaluations must be deterministic per seed (CRN support) |
| Set-piece search (P5) | Infeasible-spec rejection at validation (the optimizer learns real constraints) |
| Feature extraction (P4/P5) | Events carry features at generation time (ShotEvent embeds geometry: distance, angle, header flag, …) — no post-hoc trajectory mining |
| ML pipelines (P4) | Event vocabulary stable and typed (`restart.simulation.events` is the contract) |
| Deterministic replay | Agent tracks recorded at tick resolution; one RNG stream per sim, fixed draw order |
| Numba compatibility | All per-tick math expressible over float64/int64 arrays; no Python objects in tick state |

## 2. Throughput-risk assessment (the arithmetic, before code exists)

Per corner sim: ~6 s horizon × 50 Hz agent tick = **~300 agent ticks**; per tick: 22 agents ×
(kinematics ≈ 15 flops) + 231 separation pairs + ~22 interception updates against ≤ 1 flight
sample each ≈ **~2–4 k flops + bookkeeping**. Ball flight: integrated once (Phase-1 kernel,
~0.1 ms) + once more post-contact.

- **Phase-2 NumPy single-sim estimate:** ~300 ticks × ~30 vector ops ≈ 10⁴ NumPy calls ≈
  **5–20 ms/sim**. Fine for Phase 2 (library validation, replays) — *would miss Phase 3 budget
  by ~5–10×*, exactly as the Phase-1 NumPy path did.
- **Phase-3 fused-kernel projection:** ~300 ticks × 22 agents × ~50 ns ≈ **0.3–0.7 ms/sim**
  single-core → 10k sims ≈ 1–2 s/core, ~0.5 s on 4 cores with `prange` — comfortably inside
  the 60 s budget with ~30× headroom for contest logic and event recording.
- **Conclusion:** the risk is not the math; it is *state shape*. Hence ADR-003 d8: the SoA
  `SimProgram` contract is the Phase-2 deliverable that de-risks Phase 3. Phase 2's NumPy
  engine is the reference implementation (semantics oracle) by design.

**Tripwire (per the stop-condition in the phase brief):** if any Phase-2 design element cannot
be expressed over flat arrays (e.g., contest logic demanding per-agent Python callbacks), stop
and re-design before Phase 3 inherits it. None identified at review time.

## 3. Realism vs throughput tradeoffs (explicit, per the directive)

| Cut | Realism cost | Throughput/complexity gain | Registered as |
|---|---|---|---|
| 2.5-D agents (reach instead of airborne jump state) | Mistimed-jump dynamics approximated by timing noise | −4 state dims, no jump state machine in kernel | G-4′ |
| Precomputed flight oracle | No player-induced air disturbance | Ball integrated once, not per-agent | G-8 |
| Reaction deadlines instead of per-tick re-planning | Slightly "scripted" feel at decision boundaries | ~5× fewer decision evaluations; *more* human latency realism | G-3 |
| Gumbel-max contest (one draw) | No multi-touch scramble micro-dynamics | Branchless, single RNG draw, kernel-friendly | G-6 |
| Discrete GK save model | No dive animation realism | Replaces hardest continuous sub-problem with a calibrated logistic | G-9 |
| Soft-disc separation, no fouls | No shirt-pulling/contact fouls (real corners have them!) | O(n²) impulses avoided; noted as known fidelity gap for calibration to absorb | G-7 |
| First-contact-centric termination | Second-phase goals (~rebounds) classified, not simulated | Bounds sim horizon; Phase 3 extends behind same schema | G-10 |

## 4. Work-package decomposition (sub-agent implementation plan)

| WP | Owner | Scope (file ownership is disjoint) |
|---|---|---|
| A | Sonnet sub-agent | `restart/players/` (attributes w/ column IntEnum, Player, Team, demo teams), `restart/agents/` (kinematics kernels, interception, separation, AgentConfig), `restart/simulation/rng.py` + tests |
| B | Sonnet sub-agent | `restart/tactics/` (RoutineSpec rs/1.0, DefensiveScheme + library, Scenario, compile→SimProgram, marking assignment, FK wall) + tests |
| C | Opus sub-agent | `restart/engine/` (EngineConfig, SetPieceEngine, contests, GK model, outcomes), event-vocabulary extension, corner routine library, integration tests incl. FK feasibility, benchmarks |
| — | Fable (lead) | Design docs, review of WP output, assumptions registry G-*, verification, handoff refresh, commit |

Acceptance for the phase = roadmap Phase-2 criteria: 10 scripted corners to terminal state with
zero kinematic-invariant violations; determinism bitwise; FK compiles & runs ("configuration,
not construction"); event streams ordered and typed; benchmarks recorded.

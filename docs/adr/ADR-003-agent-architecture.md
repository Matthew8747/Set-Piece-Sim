# ADR-003 - Agent & engine architecture for Monte Carlo throughput

**Status:** Accepted · **Date:** 2026-06-12 · **Phase:** 2
**Related:** design doc 05 §3 (agent model), ADR-001/002, Phase-2 design review

## Context

Phase 2 builds the player-agent and set-piece engine layer. The binding constraint comes from
*future* phases: Phase 3 must run 10k-sim batches in < 60 s on 4 cores (≥ ~500 sims/s/core),
Phase 5 will burn ~10⁵-10⁶ sims per optimization study, and features must be extractable
cheaply at that scale. Directive from the product owner: **sacrifice small amounts of realism
before sacrificing the 100k-sim capability.**

## Decisions

1. **Two-layer behavior: scripted intents + reactive interception.** Agents follow compiled
   waypoint scripts (from Routine Spec / defensive scheme) until an information event, then the
   only "AI" is *earliest-feasible-interception* against the ball flight. No behavior trees, no
   per-tick utility AI. (G-5)

2. **Precomputed ball flight as the planning oracle.** The delivery trajectory is integrated
   once per sim (Phase-1 machinery) and sampled at the agent tick; all agents plan against the
   same sample table. Agents never re-integrate the ball, and un-contacted flight is never
   re-simulated. Aerodynamic interaction between players and ball is thereby excluded (G-8
   simplification - negligible for set pieces).

3. **Fixed 20 ms agent tick** (50 Hz physics via 4×5 ms ball sub-steps where the ball is live).
   Decision latency is modeled by *reaction deadlines* (agent ignores information until
   `t_event + reaction_time × jitter`), not by re-planning every tick. (G-3)

4. **2.5-D kinematics.** Agents move as accel- and turn-rate-limited point masses in the pitch
   plane; the vertical dimension exists only as *reach* (jump_reach_m) at contest resolution.
   No airborne agent state, no ballistic jump integration - jump quality collapses into reach +
   timing noise in the contest model. (G-1, G-2, G-4′ - a deliberate realism cut vs design doc
   05's jump-commit model; registered in the assumptions registry.)

5. **Contest resolution = feature-scored Gumbel-max draw.** All players able to reach the ball
   within the contest window (±60 ms) are contestants; score = w·(reach margin, timing,
   strength, heading, positioning) + Gumbel noise; arg-max wins (equivalent to softmax sampling,
   but branchless and kernel-friendly). Weights + temperature are named Phase-3 calibration
   knobs. (G-6)

6. **Discrete goalkeeper model.** GK contests claims like any agent (with its own envelope);
   shot stopping is a calibrated logistic save model over shot geometry/speed, not a dive
   simulation. (G-9)

7. **Soft-disc separation, no contact dynamics.** Pairwise overlap resolution at 0.4 m radius
   per tick (22 agents = 231 pairs - trivial even in a batch kernel); screens work by occupying
   space, not by physics. No fouls model. (G-7)

8. **SoA execution contract.** `tactics.compile()` produces a `SimProgram` of flat float64/int64
   arrays (attribute matrix, waypoints, triggers, marking assignments - ADR-004). The Phase-2
   engine is a single-scenario NumPy implementation over those arrays; the Phase-3 batch kernel
   is a port of the *same arrays and formulas* to Numba (the ADR-001-addendum pattern:
   reference + kernel + equivalence test), not a redesign.

9. **Determinism.** One `numpy.random.Generator` per sim, spawned as
   `Philox(SeedSequence(root_seed, spawn_key=(sim_index,)))`; every stochastic draw (delivery
   noise, reaction jitter, contest Gumbel, GK save) consumes from that stream in a fixed order.
   Same (program, seed) ⇒ bit-identical result.

10. **First-contact-centric outcome model (Phase 2 scope).** The sim resolves: delivery →
    first contact (or untouched landing) → one contact action (shot/flick/clearance/claim) →
    terminal outcome (goal/saved/off-target/cleared/keeper-claim/second-ball-att/def/out).
    Continued second-phase play is a Phase-3+ extension behind the same event schema.

## Alternatives considered

| Alternative | Rejected because |
|---|---|
| Behavior trees / utility AI per agent | Per-tick branching object logic is kernel-hostile; legibility for calibration suffers; set-piece roles are scripts + one reactive rule |
| Full 3-D agent kinematics with jump state | Adds 4+ state dims and a commit state machine for outcome-equivalent behavior at contest time; the timing-noise model captures mistiming with two parameters |
| Continuous re-planning every tick | More "alive" but ~5× the per-tick cost and *less* realistic than reaction-latency gating |
| Pairwise momentum/collision physics | O(n²) impulse resolution with tunneling headaches; screens/blocks only need space occupation |
| Event-driven (continuous-time) simulation | Elegant for sparse events, but contest windows and marking make state dense in time; fixed tick is simpler, deterministic, and batchable |

## Consequences

- Realism cuts are explicit, named (G-1…G-10), and registered in
  `docs/simulation-assumptions.md` with calibration/validation status.
- The Phase-3 kernel port is mechanical: same arrays, same formulas, prange over sims.
- Agent parameters (contest weights, noise scales, tick constants) live in `EngineConfig` /
  `AgentConfig` pydantic models - config, not code, so the calibration harness can search them.

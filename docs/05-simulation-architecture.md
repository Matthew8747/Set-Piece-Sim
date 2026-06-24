# Simulation Architecture - Restart Lab

**Version:** 0.1 · **Status:** Design review draft

This document doubles as the seed of the **Simulation Assumptions Document** (a PRD-required
deliverable): every modeling choice is stated as an explicit, numbered assumption `P-*` (physics),
`G-*` (agents), `M-*` (Monte Carlo).

---

## 1. Design philosophy

**Fidelity budget:** model only what changes set-piece outcomes, and model it explainably.
A set piece is ~4-8 seconds, one ball delivery, one or two contests, one or two shots. The
fidelity hierarchy, in order of outcome-impact:

1. Ball flight geometry (where/when the ball arrives) - **high fidelity (RK4 + drag + Magnus)**
2. Who wins the aerial/first contact - **medium fidelity (kinematic reach + skill-weighted contest)**
3. What the contact produces (shot quality) - **delegated to the real-data xG model** (see ML doc)
4. Second-ball scramble - **coarse stochastic model, explicitly labeled**

**Challenged assumption:** "more physics = more credible." False past a point - biomechanical
player models would consume the schedule and add un-validatable parameters. Players are
point-mass kinematic agents with capability envelopes; the *ball* gets the real physics. This is
also how published football-simulation literature slices it.

## 2. Ball physics model

### 2.1 Flight (per-tick forces)

State: position **r**, velocity **v**, spin vector **ω** (rad/s, body-frame-free).

```
m dv/dt = m·g  +  F_drag  +  F_magnus
F_drag   = -½ ρ A C_d |v| v
F_magnus =  ½ ρ A C_l |v|² ŝ,   ŝ = (ω × v)/|ω × v|
```

| Constant | Value | Assumption |
|---|---|---|
| Ball mass m | 0.430 kg | `P-1` FIFA Law 2 midpoint |
| Radius | 0.110 m | `P-1` |
| Air density ρ | 1.225 kg/m³ | `P-2` sea level, 15 °C; host-city altitude (Mexico City 2,240 m, ρ≈0.98) exposed as a scenario parameter - a genuinely fun WC2026 feature, since ~7% less drag/Magnus at altitude measurably changes deliveries |
| C_d | 0.25 post-critical, ramp to 0.45 below Re_crit (|v|≈12 m/s) | `P-3` smooth approximation of the drag crisis; literature-anchored |
| C_l | Spin-parameter fit: C_l = S/(2.2·S+0.7), S = r|ω|/|v| | `P-4` empirical Magnus fit; clamped S ≤ 0.6 |
| Spin decay | τ ≈ 8 s exponential | `P-5` minor over flight times ≤ 4 s |

Integrator: **RK4, fixed dt = 5 ms** for ball flight (`P-6`); error vs dt=1 ms reference pinned
< 1 cm over a 40 m delivery in golden tests. Players tick at 20 ms with interpolation.

### 2.2 Bounce & roll (`P-7..P-9`)

- Normal: v'_z = -e·v_z, **e = 0.65** dry grass (configurable 0.55-0.75).
- Tangential: Coulomb-style impulse couples horizontal velocity and spin (sliding vs rolling
  contact branch); post-bounce spin recomputed.
- Rolling: μ_roll = 0.06 deceleration until |v| < 0.2 m/s ⇒ ball dead (or out/goal events).

### 2.3 Contact events (kicks, headers, deflections, saves) (`P-10..P-13`)

All player-ball interactions are **impulse events**, not continuous contact:

- An *intent* (target point, speed, spin) is resolved into an outgoing ball state.
- **Execution noise** is the skill hook: actual outgoing velocity = intended + noise, where noise
  covariance scales inversely with the relevant skill (`delivery_skill` for kicks, `heading` for
  headers) and with difficulty (closing speed of ball, body orientation, contest pressure).
  Direction noise ~ von Mises-Fisher about intended direction; speed noise lognormal.
- Headers cap outgoing speed at `v_head_max ≈ 0.7·|v_in| + 8 m/s·heading` (`P-12`, tunable
  in calibration) - prevents physically absurd headed goals from weak positions.
- Deflections (unintentional contacts): restitution off body e_body = 0.4 with high scatter.
- Goalkeeper: catch/parry/miss discrete outcome model gated by reach kinematics (dive envelope
  from GK attributes) with probabilities conditioned on ball speed, distance, and traffic
  (`P-13`); parries produce outgoing ball with large noise → feeds second-ball model.

## 3. Agent model

### 3.1 Kinematics (`G-1..G-4`)

Point-mass with capability envelope per `player_attributes`:

- `|a| ≤ accel_ms2`, `|v| ≤ top_speed_ms`; curvature limit: max heading change rate
  ∝ agility / |v| (fast players turn wide - `G-2`).
- Reaction latency: agent re-plans only after `reaction_time_ms` from an information event
  (ball struck, flick-on) - before that it continues its previous plan (`G-3`).
- Jumping: ballistic, single jump per contest, total reach = `jump_reach_cm`; jump commit time
  ~250 ms before desired contact ⇒ mistimed jumps are possible and skill-dependent (`G-4`).

### 3.2 Decision model: scripted intents + reactive interception

Two-layer design - this is the key simplification that keeps the project tractable:

1. **Scripted layer (from Routine Spec / defensive scheme):** each agent has a role with
   waypoints and timing triggers ("start far-post run when kicker begins approach"). Decoys and
   screens are scripted intents. Defenders hold zones or track assigned marks (with `marking`-
   scaled tracking fidelity).
2. **Reactive layer (shared by everyone):** once the ball is in flight, each agent continuously
   solves *earliest feasible interception* of the ball trajectory given its kinematic envelope,
   and decides whether to abandon script for ball-attack based on role + awareness. Contest
   entry, jump timing, and contact intent come from this layer.

**No learned behavior in v1** (`G-5`): behaviors are legible, debuggable, and tunable -
properties the calibration phase needs desperately. RL-driven agents are a Tier-3 research
extension, not a foundation.

### 3.3 Aerial/ground contest resolution (`G-6`)

When ≥ 2 players can reach the ball within a contest window (±60 ms):

```
score_i = w_r·reach_margin_i + w_t·timing_i + w_s·strength_i + w_h·heading_i + w_p·position_i + ε_i
P(i wins first contact) = softmax over contestants (temperature = calibration parameter)
```

Winner executes their contact intent with contest-degraded execution noise. The weights and
temperature are **the** primary calibration knobs (§6) - flexible enough to match real first-
contact and shot rates, few enough to avoid overfitting.

### 3.4 Realism constraints (hard, tested)

No teleporting (positions integrate from bounded accelerations - property test); no double
jumps; no reaction before latency expires; goalkeepers obey the same kinematics; screens impose
path-blocking via soft collision radii between players (`G-7`: players are 0.4 m-radius soft
discs; overlap resolves with separation impulses - no ragdolls, no fouls model in v1, noted
limitation).

## 4. Tactical layer: the Routine Spec

Declarative JSON document - simultaneously the UI scenario-builder format, the optimizer's
genome, and the replay metadata. Sketch (`rs/1.0`):

```jsonc
{
  "spec_version": "rs/1.0",
  "set_piece": "corner",
  "delivery": {
    "kicker": "role:kicker",
    "type": "inswinger",                  // outswinger | inswinger | driven | floated | short
    "target": {"x": 99.2, "y": 30.5},     // meters, 105x68 frame
    "speed_ms": 24.0,
    "spin_rps": 8.0
  },
  "assignments": [
    {"role": "target_1", "start": {"x": 88, "y": 28}, "run": [{"to": {"x": 99, "y": 31}, "trigger": "kicker_approach", "delay_ms": 200}], "intent": "attack_ball"},
    {"role": "decoy_1",  "start": {"x": 90, "y": 34}, "run": [{"to": {"x": 95, "y": 38}, "trigger": "kicker_approach"}], "intent": "decoy"},
    {"role": "screen_1", "start": {"x": 97, "y": 33}, "intent": "screen", "screen_target": "opp_gk"},
    {"role": "edge_1",   "start": {"x": 85, "y": 34}, "intent": "second_ball"}
  ]
}
```

Free kicks and throw-ins are the same schema with different `set_piece`, delivery constraints
(wall placement becomes part of the defensive scheme; throw speed caps), and legality rules -
this is what makes Tier-2 expansion configuration rather than construction (validates PRD `A-3`).

Validation: JSON Schema + domain checks (positions on pitch, no offside-at-kick for free kicks,
roles resolvable from lineup, runs kinematically feasible for the assigned player - *infeasible
specs are rejected at submission, not silently "fixed"*, so the optimizer learns real constraints).

## 5. Monte Carlo engine

### 5.1 Stochastic elements (`M-1`)

Randomness enters **only** through: delivery execution noise, contact execution noise, contest
resolution, reaction-time jitter (±15%), run-timing jitter (awareness-scaled), GK decision
outcomes, second-ball resolution. Everything else is deterministic - keeps variance attributable.

### 5.2 Vectorized batch design

The 100k requirement (PRD FR-4.1) shapes the core data layout:

- **Structure-of-arrays**: state tensors shaped `(n_sims, n_players, dims)` /
  `(n_sims, ball_dims)`; the whole batch ticks in lockstep with NumPy ops; per-sim divergence
  handled by boolean masks (sims that ended early are masked out, not branched).
- Phase-structured ticking keeps masks cheap: [pre-kick] → [flight] → [contest] → [resolution
  /second ball] → [terminal]; sims advance through phases independently via mask groups.
- Hot scalar paths (contest scoring, bounce branch) JIT-compiled with Numba where profiling
  says so - **profile first, Numba second** is the rule.
- Chunking: 100k runs = 50 × 2k-sim chunks per worker task → bounded memory (~2k sims ×
  23 agents × state ≈ tens of MB), incremental progress, resumability.
- Replay storage: full trajectories kept only for a curated sample (best/median/worst xG +
  50 random) - replays are illustrations; statistics come from event logs.

Performance budget (NFR): ≥ 500 sims/s/core ⇒ 10k corner sims < 60 s on 4 cores with the API
responsive throughout. Validated by a benchmark in CI (regression gate at -20%).

### 5.3 Outcome extraction

Each sim emits a typed event log: `kick`, `first_contact(player, zone, type)`, `shot(xg_features)`,
`goal`, `save`, `clearance(zone)`, `second_ball(winner_team)`, `out_of_play`, `keeper_claim`.
KPIs in `sim_results_summary` are pure aggregations; **xG features, not goals, are the primary
shot output** - goal sampling uses the real-data xG model (ML doc §2) so simulated finishing
never drifts from reality.

### 5.4 Statistics (`M-2..M-3`)

- Proportions: Wilson 95% CIs. Derived (mean xG): BCa bootstrap, 2,000 resamples.
- Comparisons (routine A vs B): two-proportion z-test + absolute-difference CI; the UI never
  claims superiority without non-overlapping CIs or p < 0.01 (multiple-comparison-adjusted in
  optimizer leaderboards via Benjamini-Hochberg).
- Common random numbers across compared scenarios (same child-seed streams) to slash variance
  of *differences* - a quietly senior touch worth a case-study paragraph.

## 6. Calibration & validation plan (the credibility spine)

Four levels, in order; each is a roadmap gate:

| Level | Question | Method |
|---|---|---|
| **V1 Physics unit** | Does ball flight match known physics? | Golden tests vs analytic drag-free cases; drag/Magnus curves vs published wind-tunnel ranges; a recreated famous free kick (e.g. Roberto Carlos 1997) bending plausibly |
| **V2 Kinematic sanity** | Do agents move like humans? | Property tests vs envelope; sprint-time table vs published 30 m times |
| **V3 Statistical calibration** | Do 10k-run corner outcome rates match reality? | Tune contest weights/noise scales (≤ 8 named knobs, documented) until goal/shot/first-contact rates sit inside pinned real bands from `mart` data; hold-out: calibrate on WC 2022, check vs Euro 2024 |
| **V4 Face validity** | Do replays look like football to a knowledgeable viewer? | Structured review checklist (no orbiting runs, sane GK behavior, screens look like screens); failures filed as tunable issues |

Calibration knobs, their values, and before/after rate tables are published in
`docs/simulation-assumptions.md` - including misses. An honest "model under-produces far-post
headers by 2pp" note is worth more portfolio credit than silent perfection.

## 7. Module boundaries (within `restart/`)

| Module | Responsibility | Key interface |
|---|---|---|
| `physics` | Ball state evolution, contact impulse resolution | `step_ball(state, dt)`, `resolve_contact(intent, ball, noise_rng)` |
| `agents` | Kinematics, reactive interception, contest entry | `step_agents(states, plans, ball, dt)` |
| `tactics` | Routine Spec parsing/validation, scheme expansion, scenario assembly | `compile(scenario) -> SimProgram` |
| `montecarlo` | Batch loop, masks, RNG streams, event extraction, stats | `BatchRunner.run(program, n, seed) -> BatchResult` |

`tactics.compile` is the load-bearing seam: it resolves all references (players→attributes,
roles→agents, scheme→defender plans) into a self-contained `SimProgram`, so `montecarlo` knows
nothing about teams, specs, or databases.

## Assumption index (summary)

Physics `P-1..P-13`, agents `G-1..G-7`, Monte Carlo `M-1..M-3` as numbered above; the full
prose register with literature citations becomes `docs/simulation-assumptions.md` in Phase 1
and is the canonical home (this section then links rather than duplicates).

## 8. Future engine fidelity (Tier-3 research - not yet built)

The Phase-2..5 engine is **first-contact-centric** (assumption O-3): a delivery resolves to a single
first attacking contact that becomes a shot, plus a loose-ball/second-ball step. That is a
deliberate, registered fidelity cut. The following extensions are scoped here so the optimizer's
limits are explicit; each is a future engine phase, not Phase 6 (API/Workbench) work.

### 8.1 Multi-touch pass-then-shot sequences

Real set pieces routinely score off a *combination*: a cross to the back post is headed/cut back
across the six-yard box for a tap-in. The current engine cannot represent this - the first contact
terminates the play. Planned model: after an attacker wins the first contact, they may **lay off /
pass** to a better-placed teammate instead of shooting; the teammate's strike becomes the scored
shot context. A pass has a **success probability** (passer skill, distance, defender pressure,
angle); a failed pass becomes a loose ball (the existing second-ball path). This raises the xG
ceiling for routines that manufacture a tap-in and is the single biggest realism gap today.

### 8.2 Sequential decision lookahead (shoot vs pass)

With §8.1 in place, the ball-winner faces a **decision**, not a fixed action: shoot now for
`E[xG | shoot]`, or pass for `E[pass_success] · E[xG | teammate's contact]`. This is a small,
depth-limited **expectimax / game-tree search** over the post-contact phase (chess-engine in spirit,
but shallow - 1-2 plies), choosing the higher expected value while pricing in pass-failure risk.
The agent picks the action a real attacker would; the optimizer then discovers routines that *create*
the high-value second action. Must stay cheap (it runs inside the hot Monte Carlo loop) and seeded
(determinism contract).

### 8.3 Defender anticipation under partial observability

Defenders currently react to the ball and their marks only. Real defenders **anticipate** common
patterns (a back-post overload, a cut-back runner) without knowing the exact plan. Planned model: a
**noisy prior over attacker intents** (partial observability) that biases defender positioning -
strong enough to punish telegraphed routines, noisy enough that disguise/decoys still work. This
closes the loop on §8.1-8.2 so the optimizer cannot exploit omniscient-or-blind defenders.

### 8.4 Throughput note

All three increase per-sim cost, which sharpens the existing throughput constraint (ADR-006): they
should land **with or after** the fused Numba scenario kernel (ADR-003 d8), not before.

# Simulation Assumptions Registry

**Engine version:** `sim/0.1.0` · **Status:** Living document (every physics-affecting change
updates this file and bumps `restart.ENGINE_VERSION`).

Each assumption has an ID (referenced from code docstrings and design docs), the implemented
value/model, its literature anchor, and its calibration status:
**[fixed]** = physical constant, not tuned · **[knob]** = explicit Phase-3 calibration parameter
· **[simplification]** = known fidelity cut, registered honestly.

## Ball & environment

| ID | Assumption | Implementation | Anchor |
|----|-----------|----------------|--------|
| P-1 | Ball is a FIFA Quality Programme size-5: m = 0.430 kg, r = 0.110 m **[fixed]** | `BallConfig` (bounds 0.40-0.46 kg per Law 2) | IFAB Laws of the Game, Law 2; FIFA Quality Programme test ranges |
| P-2 | Uniform gravity 9.81 m/s²; still air, sea-level density 1.225 kg/m³; **altitude exposed as scenario parameter** via isothermal barometric model (scale height 8.5 km) **[fixed]** | `EnvironmentConfig`, `EnvironmentConfig.at_altitude()` | US Standard Atmosphere; WC2026 note: Estadio Azteca (2,240 m) → ρ ≈ 0.94 kg/m³, ~23 % less drag/Magnus |
| P-3 | Quadratic drag with a **smooth (logistic) drag crisis**: C_d from 0.45 (subcritical) to 0.25 (supercritical) around v_crit = 12 m/s, width 1.5 m/s **[knob: all four]** | `DragConfig`, `QuadraticDrag` | Asai et al. (2007) *Fundamental aerodynamics of the soccer ball*; Goff & Carré (2009) *Trajectory analysis of a soccer ball*, Am. J. Phys. 77; Achenbach (1972) for the sphere drag crisis. Smoothing is an idealization of the experimentally sharp transition (keeps the ODE C¹) |
| P-4 | Magnus lift via spin parameter S = rω/v: C_l = S/(aS + b), a = 2.2, b = 0.7, S clamped at 0.6 **[knob: a, b, clamp]** | `MagnusConfig`, `MagnusLift`; force direction unit(ω × v), vanishing smoothly for ω ∥ v | Empirical-fit family per Goff & Carré (2009, 2010); published fits vary materially - constants are first-class calibration targets, see test `test_roberto_carlos_1997_bends_around_the_wall` for the plausibility envelope (2-9 m deflection; reconstructions estimate ~4 m, e.g. Dupeux et al. 2010) |
| P-5 | Spin decays exponentially, τ = 8 s **[knob]**; integrated inside the state vector (dω/dt = −ω/τ) | `make_derivative` | Minor effect over ≤ 4 s flights; order-of-magnitude from flight-analysis literature |

## Integration & events

| ID | Assumption | Implementation | Anchor |
|----|-----------|----------------|--------|
| P-6 | Fixed-step classical RK4, dt = 5 ms **[fixed by ADR-002]** | `rk4_step`; `IntegratorConfig` | Validated: < 1 cm vs SciPy DOP853 (rtol 1e-10) over a 33 m spinning delivery; global error scales ~dt⁴ (convergence test); drag-free analytic match ~1e-9 m |
| P-14 | Event times/positions (apex, ground contact, plane crossings) refined by **linear interpolation within the step**; earliest crossing in a step wins **[simplification]** | `TrajectorySimulator`, batch kernel | Sub-millimeter interpolation error at 5 ms steps; root-polishing rejected as unjustified (ADR-002 d3) |
| P-15 | Goal/out-of-play decided by **ball center** crossing the plane (not "whole ball" per Law 9/10); goal mouth = |y| ≤ 3.66 m, z ≤ 2.44 m on the goal-line plane **[simplification]** | `pitch.is_in_goal_mouth`, trajectory crossing checks | Error bounded by one ball radius (11 cm); below current model fidelity; revisit if calibration shows edge effects |

## Ground interaction

| ID | Assumption | Implementation | Anchor |
|----|-----------|----------------|--------|
| P-7 | Normal restitution e = 0.65 on dry grass **[knob, range 0.55-0.75]**; contact at ball-center height z = r | `BounceConfig`, `bounce()` | Wesson, *The Science of Soccer* (bounce ch.); FIFA Quality Programme rebound test ranges |
| P-8 | Tangential bounce: **Coulomb friction impulse on contact-point slip** (couples velocity & spin) with stick/slide branch, μ = 0.40 **[knob]**; rolling regime decelerates at μ_roll·g, μ_roll = 0.06 **[knob - flagged: produces generous roll-out distances, early calibration target]**; rest below 0.2 m/s | `bounce()` (impulse derivation in module docstring), `_step_rolling` | Standard sports-ball bounce mechanics (e.g. Cross 2002, *Grip-slip behavior of a bouncing ball*, Am. J. Phys. 70) |
| P-9 | Ball inertia: thin spherical shell, I = (2/3)mr² **[fixed]**; **no twisting friction** - spin about the contact normal unchanged across bounce **[simplification]** | `BallConfig.moment_of_inertia`, `bounce()` | Shell idealization standard for footballs; energy invariant property-tested (total KE never increases across bounce, 300 random cases) |

## Deliberate exclusions (Phase 1)

| ID | Exclusion | Rationale / revisit |
|----|-----------|---------------------|
| P-10 | No wind | Stadium-level wind data unavailable & unverifiable; `ForceModel` protocol makes a wind force a ~20-line addition if a use case appears |
| P-11 | No ball deformation / knuckling (asymmetric wake at near-zero spin) | Genuinely chaotic regime; out of scope for set-piece deliveries which are struck with deliberate spin; noted as known limitation for very low-spin shots |
| P-12 | No Reynolds-dependence in C_l (Magnus) beyond the S-clamp | Data too sparse to fit responsibly; absorbed into P-4 calibration |
| P-13 | Batch engine covers launch → first ground contact only (no batch bounce chains / plane crossings yet) | Phase-3 Monte Carlo layer owns batch event extraction; single-trajectory path is event-complete today |

## Agents & engine (Phase 2, `sim/0.2.0`)

| ID | Assumption | Implementation | Status |
|----|-----------|----------------|--------|
| G-1 | Capability envelope: top speed 5.5-9.8 m/s, accel 2-8 m/s², bounds from sprint literature **[fixed rails, per-player knobs]** | `PlayerAttributes`, enforced by `step_agents`; envelope property-tested from recorded tracks | validated |
| G-2 | Turn-rate limit ∝ agility, tighter at speed **[knob]** | `step_agents` heading clamp | tested |
| G-3 | Reaction latency gates *reading* the flight; pre-committed scripted runners pay none **[knob: jitter ±15%]** | ready-time gating in engine §4 | tested |
| G-4′ | No airborne jump state: vertical = reach at contest + timing noise **[simplification vs design 05 jump-commit]** | contest model | registered |
| G-5 | Two-layer behavior: scripts + earliest-feasible interception; no behavior trees | ADR-003 d1 | by design |
| G-6 | Contest = feature-scored Gumbel-max; weights/window/scale **[knobs]**; window 0.20 s (static defenders otherwise unbeatable by arriving runners) | `EngineConfig`, `_contest_winner` | tested, uncalibrated |
| G-7 | Soft-disc separation 0.4 m, no fouls/momentum exchange **[simplification]** | `separate()` | tested |
| G-8 | Precomputed flight oracle; no player-air interaction **[simplification]** | engine flight table | by design |
| G-9 | GK: contests claims as agent + logistic save model on shot features **[knobs c0..c3]** | `_resolve_shot` | tested, uncalibrated |
| G-10 | First-contact-centric termination; untouched ball → proximity second-ball classification **[simplification]** | ADR-003 d10 | tested |
| G-11 | Delivery execution: range-solved elevation (carry factor **[knob]**), curl pre-aim compensation **[knob]**, skill-scaled direction/speed noise **[knobs]** | `_execute_delivery` | tested |
| G-12 | Header/clearance contact: P-12 speed cap, von Mises-ish aim noise by skill **[knobs]** | `_resolve_shot` | tested |
| G-13 | Interception planned once from kick-instant states (no in-flight re-planning) **[simplification]** | engine §4 | registered |

**Phase-2 honesty note:** outcome *rates* are not calibrated (keeper-claim share measurably
high; goal rate ~5% vs real 2-3%). Every rate-shaping constant above is a named `EngineConfig`
field - exactly the surface the Phase-3 calibration harness searches.

## Engine xG scoring (Phase 4, `sim/0.4.0`)

| ID | Assumption | Implementation | Status |
|----|-----------|----------------|--------|
| G-14 | When a real-data xG model is injected, an attacker first-contact shot's goal/no-goal is a **Bernoulli draw on the model-scored P(goal)** (not the placeholder geometry + GK-save logit). Non-goals split saved vs off-target by whether the shot trajectory was on frame; a goal whose geometric trajectory missed is synthesized at the aimed point so the replay is xG-consistent **[simplification]** | `engine._resolve_shot_xg`; `restart.engine.xg` | tested |
| G-15 | The simulated `ShotContext` (distance, goal angle, header flag, cone/nearest/within-3m traffic, GK geometry, under-pressure) is computed in the same metric frame and by the same closed-form feature function as `mart_setpiece_shots`, so simulated and real features are the same quantities. Documented off-manifold risk (doc 06 §2.3): simulated contexts can sit slightly outside the real-shot manifold **[simplification]** | `engine._shot_context`, `restart.engine.xg.shot_feature_vector` | tested |

**Phase-4 honesty note:** the xG models are calibrated (shipped logistic slope ≈ 1.00) but the
engine's *upstream* `[knob]`s (G-6/G-9/G-11 contest, delivery, traffic) remain uncalibrated, so
the **distribution** of simulated shot contexts is not yet validated against reality - only the
mapping from a context to P(goal) is. The G-9 GK-save logit is retained as the fallback when no
xG model is wired. Closing the upstream calibration gap stays the owed week-5 credibility task.

`ASSUMPTION D-1` (data, design doc 04 §2): StatsBomb Open Data remains available under current
terms; the raw cache is downloaded once and kept locally (permitted for use, not redistribution -
hence git-ignored). xG trains on **real data only**, never on simulator output (doc 06 §1).

## Validation evidence (V1 gate, Phase 1)

| Check | Result |
|---|---|
| Drag-free flight vs closed form | agreement ~1e-9 m over 1.5 s |
| Full model vs SciPy DOP853 (rtol 1e-10) | < 1 cm position error over a 33 m spinning delivery (P-6 acceptance) |
| RK4 convergence order | global error ratio ∈ [8, 40] on dt halving (theoretical 16) |
| Terminal velocity | matches √(2mg/ρAC_d) within 1 % |
| Spin decay | matches ω₀e^(−t/τ) within 1e-6 relative |
| Bounce energy invariant | total KE non-increasing, 300 random cases (Hypothesis) + restitution exact on normal axis |
| Roberto Carlos 1997 recreation | same strike ±spin: lateral deflection within the published-plausibility band (2-9 m; reconstructions ≈ 4 m) |
| JIT kernel ≡ NumPy reference | ≤ 1e-9 absolute agreement on 100 random flights (landing state, time, apex) |
| Throughput | 10k flights: 0.98 s single-core (target < 1 s); 1k flights ≈ 99 ms |

Calibration of all **[knob]** parameters against real corner outcome rates is the Phase-3 gate
(design doc 05 §6, roadmap Phase 3); values above are literature-anchored priors, not fitted.

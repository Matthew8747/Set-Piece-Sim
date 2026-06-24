# Product Requirements Document - Restart Lab

**Version:** 0.1 (design review draft)
**Date:** 2026-06-11
**Status:** Awaiting review

---

## 1. Vision

Restart Lab is a set-piece intelligence platform framed as the tool an analytics unit embedded
with a 2026 World Cup national team would actually use. It combines a physics-grounded match
simulator, agent-based player models, Monte Carlo experimentation, and machine-learning-driven
routine optimization to answer one question:

> **"Given our players and their defenders, what is the highest-value way to take this set piece?"**

Set pieces are the correct wedge for this product. Roughly 25-35% of goals at recent World Cups
came from set-piece situations (2022: ~31% including penalties), they are the most controllable
moments in football, and they are the area where analytics has most visibly changed elite practice
(e.g., the dedicated set-piece coach trend). A simulator is genuinely useful here in a way it is
not for open play, because the starting state is known and repeatable.

### Positioning statement

For **national-team analysts and set-piece coaches** preparing for the 2026 World Cup, who
**cannot rehearse against every opponent's defensive structure**, Restart Lab is a
**simulation and optimization platform** that **discovers, quantifies, and visualizes the
highest-xG routines against a specific opponent**, unlike **video-only analysis tools**, which
describe what happened but cannot search the space of what *could* happen.

---

## 2. Users and personas

| Persona | Needs | Primary surfaces |
|---|---|---|
| **Set-piece coach** ("Nicolas") | Concrete routines to train: who runs where, when, what delivery. Wants diagrams and replays, not statistics jargon. | Scenario Builder, Replay, Routine Report |
| **Performance analyst** ("Priya") | Opponent-specific weaknesses, confidence intervals, defensible numbers for the head coach. | Simulation Lab, Team Intelligence, Comparisons |
| **Data scientist** ("Marcus") | Model transparency, calibration evidence, reproducibility, API access. | API, model cards, experiment tracking |
| **Portfolio reviewer** (hiring manager) | Evidence of engineering depth, ML judgment, product taste - in under 10 minutes. | Live demo, case study, README |

The fourth persona is honest and load-bearing: every scoping decision in this document is made
with "demoable in 10 minutes, defensible in a 60-minute interview" as a constraint.

---

## 3. Questions the platform must answer

1. What is the optimal corner routine for Team A against Team B's defensive setup?
2. What is the optimal direct/indirect free-kick setup from a given position?
3. Which attacking players should attack which zones (and who should decoy/screen)?
4. Which delivery trajectory (target point, speed, spin) produces the highest expected goals?
5. Where do height mismatches exist between two squads, and how should they be exploited?
6. Where do pace mismatches exist, and which run patterns exploit them?
7. Which defensive structures (zonal / man / hybrid) are weakest against a given routine class?
8. How confident are we in all of the above? (Every number ships with an interval.)

---

## 4. Functional requirements

### FR-1 Physics simulation
- FR-1.1 Ball flight under gravity, quadratic drag, and Magnus force (3D spin vector).
- FR-1.2 Ground interaction: bounce (restitution), friction, spin transfer.
- FR-1.3 Contact events: kicks, headers, volleys, deflections, goalkeeper interventions -
  modeled as impulse events with skill-conditioned noise.
- FR-1.4 Deterministic replay: identical seed + inputs ⇒ identical trajectory.
- FR-1.5 All physical constants and assumptions documented in the simulation assumptions doc.

### FR-2 Agent-based players
- FR-2.1 Player state: position, velocity, orientation, airborne state.
- FR-2.2 Attribute-driven capability envelope: top speed, acceleration, reaction time, agility
  (turn-rate limit), jump reach (height + jumping), heading ability, strength, marking,
  offensive/defensive awareness.
- FR-2.3 Hard realism constraints: no teleporting, momentum-limited turning, bounded
  acceleration, reaction latency before responding to ball flight, single jump per aerial contest.
- FR-2.4 Role behaviors: target runner, decoy runner, screener, short option, edge-of-box,
  zonal defender, man-marker, goalkeeper.

### FR-3 Tactical engine
- FR-3.1 Corners: near post, far post, crowd-keeper, edge of box, short, decoy runs, screens.
- FR-3.2 Free kicks: direct, indirect, crossed, layoffs, rebound-attack patterns.
- FR-3.3 Throw-ins: long and short.
- FR-3.4 Custom routines via a declarative **Routine Spec** (JSON): delivery parameters +
  per-player assignments (start position, run path, timing trigger, role).
- FR-3.5 Defensive scheme templates: zonal, man-to-man, hybrid, with parameterized line heights
  and marking assignments.

### FR-4 Monte Carlo layer
- FR-4.1 Batch sizes of 1k / 10k / 100k runs per scenario.
- FR-4.2 Outcome metrics: goal probability, shot probability, header probability, first-contact
  probability (by team and player), defensive clearance probability, ball-recovery/second-ball
  probability, counterattack-risk proxy.
- FR-4.3 Confidence intervals (Wilson for proportions; bootstrap for derived metrics).
- FR-4.4 Asynchronous job execution with progress reporting; results persisted and addressable.

### FR-5 Machine learning
- FR-5.1 xG models for headers, volleys, first-time shots, and rebounds, trained on real
  event data, with calibration evidence.
- FR-5.2 Routine optimization over the Routine Spec space (delivery × runs × assignments),
  using the simulator as the objective function.
- FR-5.3 Method comparison is itself a deliverable: logistic regression baseline vs gradient
  boosting for xG; Bayesian optimization vs CMA-ES vs genetic algorithm for search.
- FR-5.4 Explainability: per-feature attribution for xG (SHAP); "what makes this routine good"
  narratives from a surrogate model.
- FR-5.5 Model cards for every shipped model.

### FR-6 Data platform
- FR-6.1 Reproducible ingestion of StatsBomb Open Data (international tournaments).
- FR-6.2 Player profile store: height, weight, preferred foot, pace, jumping, heading, strength -
  with per-attribute source/provenance tags.
- FR-6.3 Custom player and custom team creation.
- FR-6.4 Data dictionary covering every persisted field.

### FR-7 Application & visualization
- FR-7.1 Interactive 2D scenario builder (drag players, draw runs, set delivery).
- FR-7.2 Trajectory + player-movement replay (2D required; 3D stretch goal, see §7).
- FR-7.3 Outcome distribution charts, first-contact heatmaps, delivery-zone heatmaps.
- FR-7.4 Nation-vs-nation comparison views and exportable team reports.
- FR-7.5 REST API with OpenAPI docs; all UI features available via API.

---

## 5. Non-functional requirements

| Category | Requirement |
|---|---|
| Performance | ≥ 500 simulations/second/core for a corner scenario (5 s sim horizon); 10k-run job completes < 60 s on a 4-core machine |
| Reproducibility | Any persisted result re-derivable from (engine version, scenario hash, seed) |
| Reliability | Sim jobs survive API restarts (queue-backed); idempotent job submission |
| Security | No hardcoded secrets; env-var config; input validation on every endpoint; rate limiting; API key on mutating endpoints (see Security checklist in System Architecture §9) |
| Quality | Type hints throughout; unit + integration + E2E tests; CI green required to merge |
| Explainability | Every model and every physical assumption documented; no black-box numbers in the UI without a "how is this computed?" affordance |
| Licensing | Every data field traceable to a source whose license permits this use (see Data Pipeline §2) |

---

## 6. Success metrics

**Scientific credibility (the project fails without these):**
- Simulator calibration: simulated corner outcome rates within published real-world bands -
  goal rate per corner ~1.5-3.5%, shot rate ~20-30%, attacking first contact ~45-55%
  (bands sourced and pinned in the calibration doc during Phase 3).
- xG model: Brier score ≤ logistic baseline; calibration curve slope 0.9-1.1 on held-out data.
- Optimizer: discovers routines with statistically significant xG improvement (non-overlapping
  95% CIs) over a naive baseline routine within a fixed simulation budget.

**Product:**
- A reviewer can go from landing page → run a 1k-sim corner scenario → view replay and
  distributions in < 3 minutes without instructions.
- One-click team report (England corners vs Argentina zonal, etc.) renders as a polished,
  exportable artifact.

**Portfolio:**
- Case study writeup published; README explains the system in < 5 minutes of reading;
  live demo deployed and stable.

---

## 7. Scope and cut lines

The brief is a 6-12 month team-sized product. To stay honest about a 12-week solo build, scope
is tiered. **Tier 1 is the contract; Tiers 2-3 are sequenced stretch.**

| Tier | Contents |
|---|---|
| **Tier 1 (core, weeks 1-12)** | Corner kicks end-to-end (physics → agents → Monte Carlo → xG → Bayesian optimization → 2D UI + replay + reports). Attacking **and** defensive corner analysis. 6-8 curated national teams. Deployed demo. |
| **Tier 2 (in-roadmap stretch)** | Free kicks (direct + crossed) and long throw-ins as Routine Spec variants - engine is built to make this cheap (same delivery/contest machinery, different initial conditions and constraints). CMA-ES + GA comparison study. 3D replay (React Three Fiber). |
| **Tier 3 (post-roadmap)** | Reinforcement-learning agents, opponent-adaptive defenses, full 32-team coverage, video-derived defensive structures, multi-user accounts. |

**Challenged assumption (from the brief):** "Support corners, free kicks, and throw-ins" as
co-equal Tier-1 deliverables. Rejected: building three set-piece types shallowly produces a worse
portfolio artifact than one type built deeply with the others demonstrably cheap to add. The
Routine Spec and tactical engine are designed from day one so free kicks and throws are
*configuration*, not new subsystems - that design constraint is in Tier 1 even though the content
is Tier 2.

**Explicit non-goals (v1):** open-play simulation, penalties (no search space), live match data,
betting use cases, mobile apps, multi-tenancy/auth beyond API keys.

---

## 8. World Cup 2026 framing

- Curated launch set of national teams chosen for data richness and narrative value:
  **England, France, Argentina, Brazil, USA, Japan, Spain, Germany** (subject to data audit in
  Phase 0; minimum 6 must survive the audit).
- Canonical demo scenarios shipped with the product: *England attacking corners vs Argentina
  zonal*, *France direct free kicks*, *USA long throws*, *Brazil corner defense stress-test*.
- Player pools based on plausible 2026 squads, clearly labeled as analyst-curated projections
  (rosters are not announced at design time). `ASSUMPTION: A-1` - squad uncertainty is handled
  editorially (curated pools), not modeled.

---

## 9. Top risks (summary - full register in roadmap §11)

1. **Simulator realism** - the existential risk. Mitigation: calibration is a Phase-3 gate, not
   an afterthought; publish honest validation results either way.
2. **Scope explosion** - mitigated by tiering (§7) and per-phase acceptance criteria.
3. **Data licensing** - mitigated by Phase-0 licensing audit and provenance-tagged attributes;
   no scraped ratings data, ever.
4. **Performance of 100k runs** - mitigated by vectorized batch engine design (Simulation
   Architecture §6) and by precomputing demo results so the live demo never depends on
   on-demand heavy compute.
5. **Solo-developer bandwidth** - mitigated by vertical-slice sequencing: the project is
   shippable (demoable + writeup-able) at the end of every phase from week 5 onward.

---

## 10. Glossary

| Term | Meaning |
|---|---|
| Routine | A fully specified attacking set-piece plan: delivery + player assignments + timing |
| Routine Spec | The declarative JSON encoding of a routine (the optimizer's search space) |
| Scenario | Routine + attacking team + defending team + defensive scheme + kick position |
| First contact | First deliberate touch on the delivered ball by any player |
| Second ball | Possession contest after the first contact fails to produce a shot or clearance |
| xG | Expected goals: probability a shot results in a goal, given its context |
| Restart | Coaching term for any dead-ball resumption (the product's namesake) |

## Assumption index

- `A-1` (§8): 2026 squads are analyst-curated projections, not modeled uncertainty.
- `A-2` (§6): published set-piece base-rate bands are stable enough to calibrate against.
- `A-3` (§7): free kicks/throw-ins genuinely reuse corner machinery (validated by a design
  spike in Phase 2 - see roadmap).

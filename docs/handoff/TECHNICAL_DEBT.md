# Technical Debt (prioritized index)

**Canonical register (with origins and rationale):**
[development-guide.md §Known tech debt](../development-guide.md). This file adds *priority and
exit criteria* and is refreshed each phase. Priorities: 🔴 blocks an upcoming phase ·
🟡 scheduled · 🟢 cosmetic/monitor.

| Pri | Item | Exit criterion | Owner phase |
|---|---|---|---|
| 🔴 | Engine *upstream* `[knob]`s (contest/delivery/GK/mu_roll/Magnus) uncalibrated; simulated shot-context distribution unvalidated (goal ~5% vs 2–3% real) | [knob]s fitted to `mart_calibration_targets` real base rates; held-out check | Phase 5 (data now in hand) |
| 🔴 | Reference engine ~3 sims/s; no fused batch scenario kernel. Consequence: optimizer studies run at a scoped budget (ADR-006). **More pressing after P8** — the 7-attacker template is ~2.5× slower/sim. The keystone dependency ([roadmap](../ROADMAP-future-enhancements.md) §1) | Numba scenario kernel (ADR-003 d8) porting engine semantics; unlocks 10⁵–10⁶-sim studies and the full 500/10k reference budget | **Phase 9 (next)** |
| 🟡 | **Engine models first-contact only** — no multi-touch pass-then-shot sequences (e.g. cross to back post → cut back for a tap-in), a real high-xG set-piece pattern (O-3). Also gates **full free kicks**: P8 ships a *basic* `FreeKickGenome`, but **offside lines + off-ball runner timing** (the part that makes FK routines distinct) need this | Add a post-first-contact pass/lay-off resolution step + offside model; that teammate's shot is the scored context. Pass success = skill/pressure model | future engine phase (doc 05 / roadmap §6) |
| 🟡 | **No sequential decision lookahead** — the ball-winner always shoots; no "shoot now vs pass for higher xG next step (with pass-failure risk)" choice (chess-engine-style shallow search over the plan) | Shallow expectimax/game-tree over the post-contact phase: compare E[xG \| shoot] vs E[pass]·E[xG \| next contact]; pick the higher. Depth-limited, pass-failure-weighted | future engine phase |
| 🟡 | **Defenders have no plan anticipation / partial observability** — they react to ball + marks, not to likely routine patterns; real defenders anticipate back-post/cut-back threats without full plan knowledge | Add a defender anticipation model: a noisy prior over attacker intents (partial observability) biasing positioning, without exposing the exact routine | future engine phase |
| 🟡 | **No 3D visualization** — replay is 2D; the ball flight (z) and a static-model 3D view of a one-off / best-found routine would aid analysis | 3D replay (R3F): static player markers + the ball's 3D trajectory for a single sim and the best-found optimized routine | Phase 7 stretch (3D replay) |
| 🟡 | xG off-manifold risk (G-15): simulated contexts vs real-shot manifold unverified | Population-stability index per feature reported in the model card | Phase 5 |
| 🟡 | Physics formulas duplicated in JIT kernel vs `forces.py` | Hold: equivalence test (≤1e-9) polices drift; revisit only if a third copy appears | standing |
| 🟡 | No import-linter contract | Contract added once `restart.{agents,tactics,engine}` land (module count justifies it) | Phase 2/3 |
| 🟢 | Single-trajectory simulator ~0.4 s/run | Only if replay sampling in Phase 3 measures as a bottleneck | monitor |
| 🟢 | Starlette TestClient httpx deprecation warning | Upstream guidance settles | monitor |
| 🟢 | postcss override pin under Next 16 | Next ships patched postcss in stable | monitor (check on Next upgrades) |
| 🟢 | No app Dockerfiles | Deployment phase | Deployment (later) |
| 🟡 | **Single defensive scheme per study** — the optimizer searches against one fixed scheme; a routine could be over-fit to it | Distributionally-robust / minimax objective over a *distribution* of schemes ([roadmap](../ROADMAP-future-enhancements.md) §4) | future optimizer phase |
| 🟡 | **No evolutionary / multi-objective search** — TPE + random only; single-objective mean xG | GA/CMA-ES + NSGA-II Pareto (xG vs counterattack risk) + lineage viz; gated on the 🔴 kernel ([roadmap](../ROADMAP-future-enhancements.md) §3–4) | future optimizer phase |

## Advanced in Phase 8 (Scenario realism)

- **Corner template widened (O-2):** 4 → up to 7 attackers with off-ball zones; the "too many
  defenders vs too few attackers" imbalance is resolved (arity still fixed per study).
- **Basic free kicks:** `FreeKickGenome` over existing engine FK scaffolding (the offside/off-ball
  fidelity remains O-3 above).
- **Structured defence:** `near_post_man` scheme added to the library.
- `ENGINE_VERSION` → `sim/0.5.0`; canonical `study.json` re-baselined; observable re-baseline wrapper
  added (`scripts/rebaseline_canonical.py`).

## Closed in Phase 6 (API & Scenario Workbench)

- Derived player attributes wired into API squads — `MartSquadLoader` builds a pure `Team` from
  `mart_players`/`mart_player_attributes`; demo squads retired from the runtime.
- Idempotent Postgres mart loader shipped (`restart-etl load-postgres`, `DELETE WHERE source=X` +
  insert) beside the DuckDB loader.
- Persistence + async jobs landed (file-first repositories + in-process queue; Postgres + Arq
  drop-ins selected by config).
- shared-types hand-mirroring retired — generated from `openapi.json` with a `verify.ps1` drift gate.
- `readyz` now probes the **configured** backends (Postgres/Redis); unconfigured deps stay `skipped`
  by design.

**Still open, explicitly NOT touched by Phase 6 (carried forward):** the 🔴 engine `[knob]`
calibration, the 🔴 fused Numba scenario kernel, and the first-contact-only engine fidelity (O-3) —
all future engine phases (ADR-007 §"Explicitly NOT in scope").

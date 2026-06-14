# Case Study — England corners vs Argentina zonal

**Phase:** 5 · **Engine:** `sim/0.4.0` · **Optimizer:** `restart_opt 0.1.0` · **Date:** 2026-06-14
**Reproduce:** `restart-opt canonical --seed 0 --trials 24 --screen 40 --confirm 400 --k 3 --sens 60`

This is the worked output of System B (the routine optimizer). Methodology of record:
[docs/09-optimization-methodology.md](../09-optimization-methodology.md). The numbers below are the
committed study artifact (`optimization_studies/england-vs-argentina/study.json`). **Squads are demo
squads** (mart-derived squad selection is Phase 6), so the *findings are illustrative of the method*,
not a scouting claim about real national teams.

## Setup

- **Attack:** England (demo squad), corner from the right.
- **Defense:** Argentina (demo squad), `zonal_six_two` scheme (8 zonal + 2 markers).
- **Objective:** mean xG per simulation (real-data xG model `xg-v1`). Counterattack risk reported,
  not optimized.
- **Budget (scoped — see §"Honesty" below):** 24 screen trials per sampler at 40 sims/trial (median
  pruning on TPE), top-3 confirmed at 400 sims under common random numbers, ±10% sensitivity at
  60 sims. TPE pruned 13 of 24 trials (11 completed).

## Result 1 — TPE vs random at equal budget: **inconclusive at this budget**

| Sampler | Best screen mean xG |
|---|---|
| TPE | 0.0289 |
| Random | 0.0289 |

At this scoped budget the two samplers **tied** on best-found screen value — TPE did **not**
separate from random search. This is the honest, expected consequence of the throughput limit
(ADR-006): 24 trials × 40 noisy sims is too little signal for TPE's sample-efficiency to show, and on
a budget this small random search is a strong baseline. **Acceptance criterion 1 (TPE beats random)
is not demonstrated here** — it needs the larger budget the fused Numba kernel (deferred) would
enable. The toy-landscape test (6-D, 80 trials) confirms TPE *does* beat random when the budget is
adequate; the unit of failure here is budget, not the optimizer.

## Result 2 — Discovery beats the library baseline (✓ non-overlapping 95% CIs)

| Routine | Confirmed mean xG | 95% CI |
|---|---|---|
| Library baseline (`near_post_inswinger`) | 0.0104 | [0.0078, 0.0130] |
| Confirmed #1 (outswinger) | 0.0253 | [0.0235, 0.0271] |
| **Winner (outswinger)** | **0.0328** | **[0.0295, 0.0360]** |
| Confirmed #3 (outswinger) | 0.0294 | [0.0264, 0.0324] |

The winner's CI lower bound (0.0295) is above the baseline's upper bound (0.0130): **non-overlapping,
the winner beats the library baseline** (acceptance criterion 2 ✓). All three confirmed candidates
are **outswingers** — the signal is class-level, not a single magic routine.

## Result 3 — Insights (✓ ≥3 plain-language findings)

From the LightGBM + SHAP surrogate over the screen trials:

1. `delivery_type = outswinger` is the strongest setting for mean xG (SHAP importance 0.005).
2. `r1_intent = attack_ball` (a second ball-attacker) is the next strongest (0.003).
3. Raising `r0_delay` (a later lead-runner) tends to increase mean xG (0.003).

SHAP magnitudes are small because the budget is small (few completed trials); the *direction* is the
usable coach-facing finding: **against this zonal line, an outswinger with two genuine ball-attackers
and a late lead run is the productive class.**

## Result 4 — Anti-exploit & face-validity review

- **Bound-pinning flag (raised):** the winner's `target_y = -7.8` sits within ε of the search bound
  (-8.0). The optimizer is riding a wall — the winner should be treated with caution as a possible
  edge effect, and the **class-level** finding (outswingers) is the trustworthy takeaway, not the
  pinned-bound winner itself.
- **Face-validity ceiling (clean):** winner mean xG 0.0328 ≪ 0.5 ceiling — not a degenerate exploit.

## Result 5 — Attribute sensitivity: **report routine classes** (not player-precise)

A ±10% perturbation of the curated attributes flipped the top-1 ranking under the **+10%** case →
verdict **`report-routine-classes`** (roadmap R9). Combined with §4, the honest claim is:
**"outswinger crosses are the higher-xG class against this zonal scheme,"** not "this exact pinned
routine is optimal for these exact players."

## Acceptance scorecard

| # | Criterion | Status |
|---|---|---|
| 1 | TPE beats random at equal budget | **Not met at scoped budget** (tie); needs the deferred kernel's larger budget |
| 2 | Top routine beats library baseline, non-overlapping 95% CIs | **Met** (0.0295 > 0.0130) |
| 3 | ≥3 plain-language insights | **Met** |
| 4 | Sensitivity conclusion recorded | **Met** (report routine classes) |

## Honesty: what this study is and isn't

- **Budget-limited.** ~3 sims/s reference engine (ADR-006). The 500-screen/10k-confirm reference
  methodology was not run; this study used the scoped budget above. The pipeline, determinism,
  statistics, guards, and insight generation are all real and tested — the *sample sizes* are the
  limitation, and they are the reason criterion 1 is inconclusive.
- **Demo squads.** Not real national-team rosters (Phase 6 wires mart-derived squads).
- **First-contact model.** The engine scores a single first-contact shot; it does not yet model
  multi-touch pass-then-shoot combinations (e.g. cross to the back post cut back for a tap-in) — see
  the simulation-architecture future-work section. That fidelity gap caps how "clever" a discovered
  routine can be.

The methodological contribution — screen-then-confirm with CRN, a mandatory random baseline,
anti-exploit guards, a SHAP insight layer, and an attribute-sensitivity gate that downgrades
player-precise claims to routine classes — is the portfolio result. The optimizer is honest about
its own limits, which is the point.

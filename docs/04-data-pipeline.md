# Data Pipeline Design - Restart Lab

**Version:** 0.1 · **Status:** Design review draft

---

## 1. What the data layer must produce

1. **xG training data**: real set-piece shots with context (location, body part, freeze-frame
   defender positions, phase) → `mart_setpiece_shots`.
2. **Calibration targets**: real-world base rates for corner/free-kick outcomes (goal rate,
   shot rate, first-contact share) with sample sizes → pinned in the calibration doc.
3. **Player profiles**: capability attributes for ~25 players × 6-8 national teams, every value
   provenance-tagged → `players` + `player_attributes`.
4. **Defensive scheme priors**: how teams actually defend corners (zonal vs man counts,
   typical positions) → curated `defensive_schemes` library, informed by freeze frames.

## 2. Source audit (licensing is a Phase-0 gate)

| Source | What it offers | License reality | Verdict |
|---|---|---|---|
| **StatsBomb Open Data** (github.com/statsbomb/open-data) | Full event data incl. 360° freeze frames for: WC 2018, WC 2022, Euros, Copa, women's tournaments, select club seasons | Free for research/non-commercial with **registration + attribution required**; redistribution of raw data restricted - commit *derived* marts, not raw dumps | **Primary source.** WC 2022 + Euro 2024 alone ≈ 1,500+ corners with freeze frames |
| **FBref / Sports Reference** | Player heights, ages, aerial-duel stats, set-piece counts | ToS permits limited personal/non-commercial use; scraping rate limits (1 req/3 s published guidance); no bulk redistribution | **Secondary**: biographical fields + aggregate rates only, cached raw, attributed |
| **Understat** | Shot xG for club leagues | Unofficial API, club-only, no international coverage | **Rejected** - wrong coverage, gray access |
| **EA FC / sofifa ratings** | Ready-made attribute ratings | EA IP; scraping violates ToS; portfolio = public commercial showcase | **Rejected outright.** This is the trap the brief's "FIFA datasets" line walks into - "FIFA dataset" on Kaggle = EA game data, not usable |
| **football-data.org / openfootball** | Fixtures, squads, results | Free tiers / open | **Tertiary**: squad lists, team metadata |
| **Wikipedia/Wikidata** | Heights, DOB, positions | CC BY-SA | **Fallback** for biographical gaps, cited |

`ASSUMPTION D-1:` StatsBomb open data remains available under current terms through the project.
Mitigation: raw cache is downloaded once and kept locally (permitted for use, not redistribution).

## 3. Player attribute derivation (the honest answer to "use real player data")

There is **no licensed source of game-style ratings**. Instead, attributes are *derived* from
observable data with a documented method per attribute - which is more defensible in an interview
than any scraped rating, and mirrors what real club data departments do.

| Attribute | Derivation method | Source |
|---|---|---|
| `height_cm`, `weight_kg`, `preferred_foot` | Direct lookup | FBref/Wikidata |
| `top_speed_ms` | Position-group prior, adjusted by carry-speed percentiles where event data allows; else prior + analyst adjustment | StatsBomb-derived + priors |
| `accel_ms2` | Scaled from top speed by position-group curve (sprint literature: elite 6-8 m/s² peak) | Literature priors |
| `jump_reach_cm` | `standing_reach(height) + vertical_jump(position prior, aerial-win adjustment)` | Height + FBref aerial duels |
| `heading` | Aerial duel win rate, shrunk toward position mean (empirical-Bayes; small samples) | FBref/StatsBomb |
| `delivery_skill` | Set-piece delivery completion rate to target zones | StatsBomb events |
| `marking`, `awareness_*` | Position-group priors + analyst curation, explicitly tagged `provenance: curated` | Curated |
| `reaction_time_ms` | Population prior (200-300 ms) with small skill adjustment; **not** pretended to be measurable from event data | Literature |

Every value carries `{source, method, license}` in `player_attributes.provenance`. The UI renders
a provenance badge - turning a licensing constraint into a credibility feature.

**Sensitivity guardrail:** because several attributes are priors, Phase 5 includes a sensitivity
analysis (vary curated attributes ±10%, measure optimizer-ranking stability). If rankings flip on
±10% noise, the platform reports routine *classes*, not player-precise prescriptions.

## 4. Pipeline architecture

```
            ┌──────────── etl (Python package, CLI: `restart-etl`) ────────────┐
sources ──▶ │ RAW (immutable cache)  ──▶  STAGING (typed Parquet)  ──▶  MARTS   │ ──▶ Postgres
            │ data/raw/statsbomb/...      data/staging/*.parquet      (SQL)     │      + pinned
            │ exact API/file payloads     pydantic-validated,         loaders   │      calibration
            │ + manifest (url, sha,       standardized 105×68m        + tests   │      targets
            │   fetched_at, license)      coords, one row=one event             │
            └────────────────────────────────────────────────────────────────────┘
```

- **Raw**: byte-exact source payloads + manifest. Never edited. Git-ignored (size + license);
  re-fetchable via `restart-etl fetch statsbomb --competitions wc2022,euro2024`.
- **Staging**: typed, unit-standardized Parquet. All coordinate systems normalized to
  **105×68 m, origin at pitch center, attack left→right** (single most bug-prone transform in
  football data - owned in exactly one module, `etl/transforms/coords.py`, property-tested).
- **Marts**: the four products in §1, loaded idempotently (`DELETE WHERE source=X` + insert,
  in a transaction).
- **Orchestration**: plain CLI + Makefile targets, run locally and in a weekly CI job.
  **Challenged assumption:** "ETL ⇒ Airflow/dbt/Dagster." Rejected for v1 - a handful of
  batch jobs over static sources doesn't justify an orchestrator; a `restart-etl all` command
  that rebuilds the world from raw in < 10 min is the better reproducibility story. dbt
  **(reversible)** if mart SQL grows past ~5 models.

## 5. Data quality gates (run in CI on every pipeline change)

- **Schema tests**: pydantic at staging boundaries; column types/nullability pinned.
- **Distribution tests**: shot coordinates within pitch bounds; goal rate per competition within
  historical bands; freeze-frame player counts plausible (≤ 22); flag-don't-fail thresholds for
  drift, hard-fail for impossibilities.
- **Reconciliation**: corner counts per match vs published match stats for a sampled set.
- **License audit test**: every mart row's `source` ∈ approved list; build fails otherwise -
  licensing enforced *mechanically*, not by policy doc.
- **Reproducibility test**: `restart-etl all` from raw produces marts with pinned row-count
  ranges and stable content hash for a frozen raw snapshot.

## 6. Data dictionary

Maintained as `docs/data-dictionary.md`, generated partly from pydantic models (single source of
truth) + hand-written semantics. Every field: name, type, units, source, license, transformation.
Acceptance: no field reachable from the API that is absent from the dictionary (CI check walks
OpenAPI schema ∪ mart columns).

## 7. Alternatives considered

| Decision | Alternative | Why rejected |
|---|---|---|
| StatsBomb-primary | Build from FBref aggregates only | No freeze frames ⇒ no defender-aware xG features, no defensive-scheme priors |
| Derived attributes | Scraped EA ratings | License-fatal for a public portfolio; also unexplainable provenance |
| Parquet staging | CSV staging | Types, compression, DuckDB synergy |
| Weekly CI refresh | Real-time feeds | Sources are static archives; "real-time" is fake work here |

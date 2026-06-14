# Technical Debt (prioritized index)

**Canonical register (with origins and rationale):**
[development-guide.md §Known tech debt](../development-guide.md). This file adds *priority and
exit criteria* and is refreshed each phase. Priorities: 🔴 blocks an upcoming phase ·
🟡 scheduled · 🟢 cosmetic/monitor.

| Pri | Item | Exit criterion | Owner phase |
|---|---|---|---|
| 🔴 | Engine *upstream* `[knob]`s (contest/delivery/GK/mu_roll/Magnus) uncalibrated; simulated shot-context distribution unvalidated (goal ~5% vs 2–3% real) | [knob]s fitted to `mart_calibration_targets` real base rates; held-out check | Phase 5 (data now in hand) |
| 🔴 | Reference engine ~3 sims/s; no fused batch scenario kernel | Numba scenario kernel (ADR-003 d8) porting engine semantics; needed before Phase-5 optimization studies (10⁵–10⁶ sims) | Phase 5 |
| 🟡 | xG off-manifold risk (G-15): simulated contexts vs real-shot manifold unverified | Population-stability index per feature reported in the model card | Phase 5 |
| 🟡 | Derived player attributes not wired into API squads (still demo squads) | Squad selection from `mart_players`/`mart_player_attributes` via persistence layer | Phase 6 |
| 🟡 | Marts are Parquet + file-based DuckDB; no Postgres loaders yet | `DELETE WHERE source=X` + insert idempotent Postgres loaders (drop-in) | Phase 6 |
| 🟡 | API catalog uses fixed demo squads; no persistence/custom routines/async jobs | Postgres + Arq worker + real teams | Phase 6 |
| 🟡 | shared-types DTOs hand-mirrored (now 8 interfaces) | OpenAPI codegen | Phase 6 |
| 🟡 | Physics formulas duplicated in JIT kernel vs `forces.py` | Hold: equivalence test (≤1e-9) polices drift; revisit only if a third copy appears | standing |
| 🟡 | No import-linter contract | Contract added once `restart.{agents,tactics,engine}` land (module count justifies it) | Phase 2/3 |
| 🟡 | `shared-types` hand-mirrored | OpenAPI codegen when domain endpoints land | Phase 6 |
| 🟡 | `readyz` reports `skipped` checks | Real Postgres/Redis probes when consumers exist | Phase 4/6 |
| 🟢 | Single-trajectory simulator ~0.4 s/run | Only if replay sampling in Phase 3 measures as a bottleneck | monitor |
| 🟢 | Starlette TestClient httpx deprecation warning | Upstream guidance settles | monitor |
| 🟢 | postcss override pin under Next 16 | Next ships patched postcss in stable | monitor (check on Next upgrades) |
| 🟢 | No app Dockerfiles | Deployment phase | Phase 8 |

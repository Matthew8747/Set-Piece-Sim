# Technical Debt (prioritized index)

**Canonical register (with origins and rationale):**
[development-guide.md §Known tech debt](../development-guide.md). This file adds *priority and
exit criteria* and is refreshed each phase. Priorities: 🔴 blocks an upcoming phase ·
🟡 scheduled · 🟢 cosmetic/monitor.

| Pri | Item | Exit criterion | Owner phase |
|---|---|---|---|
| 🔴 | `mu_roll`, Magnus constants, contest/agent/GK parameters uncalibrated (goal ~5% vs 2–3% real) | All [knob] params fitted to real corner base rates; held-out check vs Euro 2024 | Phase 4–5 (data first) |
| 🔴 | Reference engine ~3 sims/s; no fused batch scenario kernel | Numba scenario kernel (ADR-003 d8) porting engine semantics; needed before Phase-5 optimization studies (10⁵–10⁶ sims) | Phase 4/5 |
| 🟡 | API catalog uses fixed demo squads; no persistence/custom routines/async jobs | Postgres + Arq worker + real teams | Phase 4/6 |
| 🟡 | shared-types DTOs hand-mirrored (now 8 interfaces) | OpenAPI codegen | Phase 6 |
| 🟡 | Physics formulas duplicated in JIT kernel vs `forces.py` | Hold: equivalence test (≤1e-9) polices drift; revisit only if a third copy appears | standing |
| 🟡 | No import-linter contract | Contract added once `restart.{agents,tactics,engine}` land (module count justifies it) | Phase 2/3 |
| 🟡 | `shared-types` hand-mirrored | OpenAPI codegen when domain endpoints land | Phase 6 |
| 🟡 | `readyz` reports `skipped` checks | Real Postgres/Redis probes when consumers exist | Phase 4/6 |
| 🟢 | Single-trajectory simulator ~0.4 s/run | Only if replay sampling in Phase 3 measures as a bottleneck | monitor |
| 🟢 | Starlette TestClient httpx deprecation warning | Upstream guidance settles | monitor |
| 🟢 | postcss override pin under Next 16 | Next ships patched postcss in stable | monitor (check on Next upgrades) |
| 🟢 | No app Dockerfiles | Deployment phase | Phase 8 |

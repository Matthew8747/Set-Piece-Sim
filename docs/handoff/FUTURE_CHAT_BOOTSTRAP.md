# Bootstrap for a New Claude Session (or new contributor)

You are joining **Restart Lab**: an AI-assisted set-piece optimization platform for FIFA World
Cup 2026. Physics simulation + agent-based players + Monte Carlo + ML routine search +
analyst-grade web UI. Solo-developer, portfolio-grade standards, phase-gated delivery.

## Read in this order (15 minutes)

1. [PROJECT_STATUS.md](PROJECT_STATUS.md) — where we are right now (1 min)
2. [PHASE_HANDOFF.md](PHASE_HANDOFF.md) — what just shipped, what's next, open decisions (3 min)
3. [ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md) + [ADR_SUMMARY.md](ADR_SUMMARY.md) — how
   the system is shaped and why (5 min)
4. [../08-roadmap.md](../08-roadmap.md) — the phase you are about to build, in its 7-part format
5. Deep-dive only what your phase touches: design docs `01–07`, the
   [assumptions registry](../simulation-assumptions.md), the
   [development guide](../development-guide.md)

## Non-negotiable working rules

- **Phase discipline:** execute one phase at a time; stop for review after each. Never start
  coding before the phase's design/ADR work is recorded.
- **Quality gates:** `./scripts/verify.sh` (or `scripts/verify.ps1`) must be green before any
  commit — it mirrors CI exactly (ruff, black, mypy --strict, pytest, next build, eslint, tsc,
  vitest, prettier). `uv` manages Python (3.12 pinned); npm workspaces manage TS.
- **Dependency rule:** `packages/simulation-core` (`restart`) is pure domain — no web/DB/IO
  imports, ever. `apps/backend` (`restart_api`) is a thin adapter.
- **Physics changes** bump `restart.ENGINE_VERSION` and update
  [simulation-assumptions.md](../simulation-assumptions.md) (P-/G-numbered, citation-anchored).
- **Throughput first:** the platform must run 100k+ Monte Carlo sims. Prefer SoA arrays +
  (measured) Numba kernels over object-per-entity designs; NumPy reference implementations stay
  as equivalence-tested oracles (see ADR-001 addendum precedent).
- **Determinism:** seed in ⇒ bit-identical results out. RNG = NumPy Philox via SeedSequence
  spawning; one production code path per computation.
- **Docs move with code:** CHANGELOG (Unreleased), tech-debt register
  ([development guide](../development-guide.md)), this handoff package at every phase end.
- **Licensing:** no scraped ratings data (EA/sofifa = forbidden); StatsBomb Open Data with
  attribution; every player attribute provenance-tagged.

## How work is organized

- Branch per phase (`feat/phaseN-…`), merged to `main` on approval. Commits carry
  `Co-Authored-By: Claude <model> <noreply@anthropic.com>`.
- Tests live in `packages/*/tests` + `apps/backend/tests` + root `tests/` (cross-package);
  namespace-style (no `__init__.py`), pytest importlib mode.
- Benchmarks: pytest-benchmark under `packages/simulation-core/tests/benchmarks/`; throughput
  gates print measured numbers into CI logs.

## Next recommended actions

See [PHASE_HANDOFF.md](PHASE_HANDOFF.md) §"Next phase" — it is always the authoritative
"what to do next".

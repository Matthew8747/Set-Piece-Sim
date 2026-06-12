# Development Guide

How to work on Restart Lab day to day. Companion to [setup-guide.md](setup-guide.md).

## Command reference

| Task | Command |
|---|---|
| Everything CI runs | `./scripts/verify.sh` / `powershell -File scripts/verify.ps1` |
| Python lint / format | `uv run ruff check .` · `uv run black .` |
| Python typecheck | `uv run mypy` (strict; config in root `pyproject.toml`) |
| Python tests | `uv run pytest` (`-m integration` for cross-package only) |
| Frontend dev server | `npm run dev -w apps/frontend` |
| Frontend lint / types / tests | `npm run lint` · `npm run typecheck` · `npm run test` |
| Format TS/JSON/CSS | `npm run format` |
| Add a Python dep | `uv add <pkg> --package restart-backend` (or `restart-simulation-core`) |
| Add a frontend dep | `npm install <pkg> -w apps/frontend` |

## Architecture rules (enforced, not aspirational)

1. **`packages/simulation-core` (`restart`) is pure domain.** It may import numpy and the
   standard library — never FastAPI, SQLAlchemy, httpx, or anything from `apps/`.
   (import-linter contract lands with the first adapter in Phase 1; until then PR review owns it.)
2. **`apps/backend` (`restart_api`) is a web adapter.** Routers translate DTOs ⇄ domain calls.
   If you're writing an algorithm in `restart_api`, it belongs in `restart`.
3. **DTOs at the boundary.** Domain objects never serialize to JSON directly; pydantic models in
   `restart_api/schemas.py` are the contract, mirrored by hand in `packages/shared-types`
   (tech debt: OpenAPI codegen planned for Phase 6 — see Known tech debt).
4. **Engine versioning.** Any change to simulation behavior bumps `restart.ENGINE_VERSION`.

## Conventions & decisions

- **Python 3.12** pinned (`.python-version`): Numba compatibility headroom for the physics
  phases; revisit at Phase 3.
- **Ruff lints, Black formats.** Ruff's formatter could replace Black, but the brief specifies
  both; the split configuration (`E501` ignored in Ruff) is the standard non-conflicting setup.
- **Test directories are namespace-style** (no `__init__.py`) with pytest
  `--import-mode=importlib`: this is what lets one strict mypy run cover three `tests/` trees
  without duplicate-module collisions.
- **Pre-commit is fast-only** (whitespace, ruff, black, private-key detection). mypy, pytest,
  eslint, vitest, and next build are CI gates — keeping commits snappy locally while CI stays
  authoritative.
- **Frontend tests use Vitest globals** (`globals: true`): required by Testing Library's
  auto-cleanup between tests.
- **`npm overrides` pins postcss ≥ 8.5.10** at the root: Next 16 stable bundles a postcss
  affected by GHSA-qx2v-qp2m-jg93; the override force-resolves it and `next build` verifies
  compatibility in CI. Remove when Next ships the fix in stable (check on each Next upgrade).

## Security ground rules

- No secrets in code, config files, or tests — environment variables only (`RESTART_` prefix;
  `SecretStr` for anything sensitive). `.env.example` documents every variable.
- The credentials in `infra/docker-compose.yml` are local-dev only by policy: the services bind
  to 127.0.0.1 and those values must never appear in any deployed environment.
- `npm audit` / dependency hygiene is part of verification; CI fails on lint, types, or tests —
  vulnerability scanning gets a dedicated job when the first deployment lands (Phase 8).

## Known tech debt

| Item | Introduced | Why accepted | Exit plan |
|---|---|---|---|
| `shared-types` mirrors DTOs by hand | P0 | 3 DTOs today; codegen infra isn't worth it yet | OpenAPI codegen when domain endpoints land (Phase 6) |
| No import-linter contract yet | P0 | Core purity held by review so far | Add in Phase 2 when agents/tactics multiply module count |
| Starlette TestClient deprecation warning (`httpx` → `httpx2`) | P0 | Functional; upstream migration is young | Migrate test transport when FastAPI's guidance settles |
| postcss `overrides` pin | P0 | Upstream Next 16 stable not yet patched | Drop on first Next release containing the fix |
| `readyz` checks report `skipped` | P0 | No Postgres/Redis consumers exist yet | Real checks wired in Phase 4/6 |
| No Dockerfile for the apps themselves | P0 | Nothing to deploy yet | Phase 8 (deployment) |
| Single-trajectory simulator is slow (~0.4 s/trajectory) | P1 | It's the replay/analysis path, not the Monte Carlo path; readability is its job | Acceptable until Phase 3 replay sampling; fuse a kernel variant only if profiling demands |
| Physics formulas duplicated in JIT kernel (`_kernels.py`) vs `forces.py` | P1 | Numba can't call the class-based force objects; duplication is the cost of the 6.9× speedup | Kernel↔reference equivalence test (1e-9) fails CI on any drift — change both together |
| Batch engine stops at first ground contact (no bounce chains / plane crossings) | P1 | Phase-3 Monte Carlo layer owns batch event extraction (P-13) | Phase 3 |
| `mu_roll = 0.06` produces generous roll-out distances | P1 | Literature-anchored prior; flagged during smoke testing | Early Phase-3 calibration target (P-8) |
| Magnus constants (P-4) are priors with wide literature spread | P1 | Plausibility-banded by the Roberto Carlos test | Phase-3 calibration; constants are config, not code |
| Engine outcome rates uncalibrated (keeper-claim high, goal ~5%) | P2 | All rate-shaping constants are named EngineConfig knobs; calibration is Phase 3's whole job | Phase-3 calibration vs real corner base rates |
| Interception planned once at kick (G-13), no in-flight re-planning | P2 | One (n,m) solve per sim; corner timescales forgive it | Revisit only if Phase-3 face-validity flags it |
| Engine is single-sim NumPy (~30-80 ms/sim) | P2 | It is the reference implementation by design (ADR-003 d8) | Phase-3 fused batch kernel ports its semantics |

## Updating documentation

Documentation reflects current implementation — that's a merge requirement, not a suggestion:

- Behavior change → update the relevant design doc section and this guide if conventions moved.
- New endpoint → API docs (OpenAPI is generated; worked examples live in docs from Phase 6).
- New simulation assumption → `docs/05-simulation-architecture.md` assumption registry
  (P-/G-/M-numbered).
- Every PR updates `CHANGELOG.md` under **Unreleased**.

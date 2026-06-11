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

## Known tech debt (Phase 0)

| Item | Why accepted | Exit plan |
|---|---|---|
| `shared-types` mirrors DTOs by hand | 3 DTOs today; codegen infra isn't worth it yet | OpenAPI codegen when domain endpoints land (Phase 6) |
| No import-linter contract yet | Nothing to violate: core has no adapters | Add with first physics module (Phase 1) |
| Starlette TestClient deprecation warning (`httpx` → `httpx2`) | Functional; upstream migration is young | Migrate test transport when FastAPI's guidance settles |
| postcss `overrides` pin | Upstream Next 16 stable not yet patched | Drop on first Next release containing the fix |
| `readyz` checks report `skipped` | No Postgres/Redis consumers exist yet | Real checks wired in Phase 4/6 |
| No Dockerfile for the apps themselves | Nothing to deploy yet | Phase 8 (deployment) |

## Updating documentation

Documentation reflects current implementation — that's a merge requirement, not a suggestion:

- Behavior change → update the relevant design doc section and this guide if conventions moved.
- New endpoint → API docs (OpenAPI is generated; worked examples live in docs from Phase 6).
- New simulation assumption → `docs/05-simulation-architecture.md` assumption registry
  (P-/G-/M-numbered).
- Every PR updates `CHANGELOG.md` under **Unreleased**.

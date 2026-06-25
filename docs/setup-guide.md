# Setup Guide

From zero to a fully verified local environment. Last validated: 2026-06-11 (Phase 0).

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | ≥ 0.5 | Manages Python itself (3.12 is pinned via `.python-version`) and the workspace. You do **not** need a system Python. |
| Node.js | ≥ 24 | npm ships with it; workspaces are configured at the repo root |
| Git | ≥ 2.30 | |
| Docker | any recent | Optional in Phase 0. `infra/docker-compose.yml` provides Postgres 16 + Redis 7 for later phases |

## 2. Install

```bash
git clone <repo-url>
cd Set-Piece-Sim

cp .env.example .env       # then edit if needed; defaults work for local dev
uv sync --all-packages     # creates .venv with Python 3.12, installs both packages editable
npm install                # installs frontend + shared-types workspaces
uv run pre-commit install  # registers fast lint/format hooks on git commit
```

`.env` is git-ignored. Production environments never use files - secrets are injected by the
hosting platform (see the security checklist in
[02-system-architecture.md §9](02-system-architecture.md)).

## 3. Verify

```bash
./scripts/verify.sh                      # macOS/Linux/WSL
powershell -File scripts/verify.ps1      # Windows
```

This runs exactly what CI runs: ruff, black, mypy (strict), pytest, next build, eslint, tsc,
vitest, prettier. All steps must pass on a clean clone - if they don't, that's a bug; please
open an issue.

## 4. Run

```bash
# API (FastAPI + uvicorn) on http://localhost:8000 - docs at /docs
uv run uvicorn restart_api.main:app --reload --app-dir apps/backend/src

# Frontend (Next.js) on http://localhost:3000
npm run dev -w apps/frontend

# Infrastructure for later phases (not consumed by Phase 0 code):
docker compose -f infra/docker-compose.yml up -d
```

Smoke checks:

```bash
curl http://localhost:8000/healthz
# {"status":"ok","api_version":"0.1.0","engine_version":"sim/0.0.1"}
curl http://localhost:8000/api/v1/meta
# {"api_version":"0.1.0","engine_version":"sim/0.0.1","environment":"dev"}
```

## 5. Troubleshooting

- **`uv python install` fails with "Missing expected target directory … minor version link"** -
  observed once on Windows; the interpreter is usually installed despite the error. Run
  `uv python list --only-installed`; if 3.12.x appears, `uv sync` will proceed fine.
- **mypy "Duplicate module named tests"** - you added an `__init__.py` to a tests directory.
  Test dirs are namespace-style by design (see development guide).
- **Vitest can't resolve `@/...` imports** - the alias lives in `apps/frontend/vitest.config.ts`
  (Vite does not read tsconfig paths); keep both in sync.

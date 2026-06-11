# Changelog

All notable changes to Restart Lab. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [SemVer](https://semver.org/) per package (the simulation engine additionally
carries its own `ENGINE_VERSION`, surfaced at `/healthz`).

## [Unreleased]

### Added — Phase 0: Repository Foundation (2026-06-11)

- Monorepo: uv workspace (Python 3.12) + npm workspaces under one roof.
- `packages/simulation-core` (`restart`): pure-domain package with the canonical 105×68 m
  coordinate frame, pitch geometry constants, `ENGINE_VERSION`, and `py.typed`.
- `apps/backend` (`restart_api`): FastAPI skeleton — app factory with settings injection,
  `RESTART_`-prefixed pydantic-settings (SecretStr secrets, no credentialed defaults),
  `/healthz`, `/readyz`, `/api/v1/meta`, CORS, typed DTOs.
- `apps/frontend`: Next.js 16 (App Router, Turbopack) + TypeScript strict + Tailwind v4,
  dark "match-ops" design tokens seeded, Vitest + Testing Library harness.
- `packages/shared-types`: TypeScript mirrors of the API contract, consumed source-form via
  `transpilePackages`.
- Tooling: ruff, black, mypy (strict), pytest (importlib mode), eslint (flat config),
  prettier, pre-commit hooks.
- CI: GitHub Actions — python job (ruff/black/mypy/pytest) + frontend job
  (build/eslint/tsc/vitest/prettier).
- `scripts/verify.{sh,ps1}`: the full CI suite, runnable locally on any OS.
- `infra/docker-compose.yml`: Postgres 16 + Redis 7 (localhost-bound) for later phases.
- Data lake skeleton (`data/raw|staging|marts`, git-ignored) with layout README.
- Documentation: README quickstart, setup guide, development guide, contributing guide;
  design package (docs/01–08) updated to as-built layout.

### Security

- npm `overrides` forces postcss ≥ 8.5.10 (GHSA-qx2v-qp2m-jg93) under Next 16 stable;
  0 `npm audit` findings at commit time.
- Secrets policy enforced from the first commit: env-only config, `.env.example` template,
  `detect-private-key` pre-commit hook.

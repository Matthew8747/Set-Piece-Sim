# Contributing

Restart Lab is a solo portfolio project, but it runs on team discipline — the process below is
the contract whether the contributor is the author or a guest.

## Workflow

1. Branch from `main` (`feat/...`, `fix/...`, `docs/...`).
2. Keep commits scoped; write messages in imperative mood with a body explaining *why*.
3. Run `./scripts/verify.sh` (or `scripts/verify.ps1`) before pushing — it is exactly CI.
4. Open a PR. CI (lint, strict types, tests, build, format) must be green to merge.
5. Update `CHANGELOG.md` (Unreleased section) and any documentation your change makes stale —
   stale docs are treated as test failures.

## Standards (the short version)

- **Python**: typed everywhere, mypy strict, ruff + black clean. Domain logic only in
  `packages/simulation-core`; web concerns only in `apps/backend`.
- **TypeScript**: strict tsconfig, eslint + prettier clean.
- **Tests are part of the feature.** Unit tests for logic, integration tests across seams,
  edge cases (boundaries, NaN, invalid input) explicitly covered.
- **Security**: no secrets anywhere in the repo; environment variables via `.env`
  (see `.env.example`); `SecretStr` for sensitive settings.
- **Simulation changes** bump `restart.ENGINE_VERSION` and update the assumption registry in
  `docs/05-simulation-architecture.md`.

Details and rationale: [docs/development-guide.md](docs/development-guide.md).

## Code review checklist

- Does the dependency direction hold (adapters → domain, never the reverse)?
- Is every new public function typed and tested?
- Did documentation move with the code?
- Would this decision be defensible in an interview? If it needs a paragraph of apology in the
  PR description, redesign it.

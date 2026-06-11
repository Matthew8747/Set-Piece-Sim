#!/usr/bin/env bash
# Full local verification - mirrors .github/workflows/ci.yml exactly.
# Usage: ./scripts/verify.sh   (from the repository root)
set -euo pipefail

step() { printf '\n==> %s\n' "$1"; }

step "uv sync";          uv sync --all-packages
step "ruff check";       uv run ruff check .
step "black --check";    uv run black --check .
step "mypy";             uv run mypy
step "pytest";           uv run pytest

step "npm install";      npm install
step "next build";       npm run build
step "eslint";           npm run lint
step "tsc --noEmit";     npm run typecheck
step "vitest";           npm run test
step "prettier --check"; npm run format:check

printf '\nAll verification steps passed.\n'

# Full local verification - mirrors .github/workflows/ci.yml exactly.
# Usage: powershell -File scripts/verify.ps1   (runnable from anywhere)
$ErrorActionPreference = "Stop"

# Always run from the repository root. ruff/black are invoked with "." and mypy
# resolves namespace-package module names relative to CWD; running from a subdir
# (e.g. scripts/) makes ruff/black see no files and mypy mis-map modules to
# "__main__". Pin CWD so the result never depends on where this is launched.
Set-Location (Split-Path $PSScriptRoot -Parent)

function Invoke-Step {
    param([string]$Name, [scriptblock]$Cmd)
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Cmd
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $Name" -ForegroundColor Red
        exit 1
    }
}

Invoke-Step "uv sync"            { uv sync --all-packages }
Invoke-Step "ruff check"         { uv run ruff check . }
Invoke-Step "black --check"      { uv run black --check . }
Invoke-Step "mypy"               { uv run mypy }
Invoke-Step "pytest"             { uv run pytest }

Invoke-Step "npm install"        { npm install }
Invoke-Step "next build"         { npm run build }
Invoke-Step "eslint"             { npm run lint }
Invoke-Step "tsc --noEmit"       { npm run typecheck }
Invoke-Step "vitest"             { npm run test }
Invoke-Step "prettier --check"   { npm run format:check }

Write-Host "All verification steps passed." -ForegroundColor Green

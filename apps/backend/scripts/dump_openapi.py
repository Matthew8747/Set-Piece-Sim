"""Write the API's OpenAPI document to apps/backend/openapi.json.

This committed artifact is the source for the generated TypeScript client
(``packages/shared-types``); CI regenerates and diffs it so the contract and the
DTO types can never silently drift (ADR-007 d6).

Run: ``uv run python apps/backend/scripts/dump_openapi.py``
"""

from __future__ import annotations

import json
from pathlib import Path

from restart_api.main import create_app
from restart_api.settings import Settings


def main() -> None:
    app = create_app(Settings(app_env="test"))
    spec = app.openapi()
    out = Path(__file__).resolve().parents[1] / "openapi.json"
    out.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

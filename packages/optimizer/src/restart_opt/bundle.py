"""Load the committed xG bundle and build an xG-enabled Monte Carlo runner.

The optimizer objective is mean xG, so the engine must carry the real-data xG
model. The bundle is the small committed coefficient artifact under ``models/``
(restart_ml.artifacts writes it). We load it with the *pure* ``from_dict`` — no
``restart_ml`` import, so the optimizer never pulls the training stack.
"""

from __future__ import annotations

import json
from pathlib import Path

from restart.engine import SetPieceEngine
from restart.engine.xg import XGModelBundle
from restart.montecarlo.runner import MonteCarloRunner


def default_bundle_path() -> Path:
    """models/xg-v1.json at the repo root (committed; data/ is git-ignored)."""
    here = Path(__file__).resolve()
    # packages/optimizer/src/restart_opt/bundle.py -> repo root is parents[4].
    candidate = here.parents[4] / "models" / "xg-v1.json"
    if candidate.is_file():
        return candidate
    return Path("models") / "xg-v1.json"  # fall back to cwd-relative


def load_bundle(path: Path | None = None) -> XGModelBundle:
    p = path if path is not None else default_bundle_path()
    payload = json.loads(p.read_text(encoding="utf-8"))
    return XGModelBundle.from_dict(payload["bundle"])


def xg_engine(bundle: XGModelBundle | None = None, path: Path | None = None) -> SetPieceEngine:
    return SetPieceEngine(xg_scorer=bundle if bundle is not None else load_bundle(path))


def xg_runner(bundle: XGModelBundle | None = None, path: Path | None = None) -> MonteCarloRunner:
    return MonteCarloRunner(engine=xg_engine(bundle, path))

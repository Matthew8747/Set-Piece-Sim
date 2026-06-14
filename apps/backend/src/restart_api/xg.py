"""Load the active xG bundle for engine injection (adapter layer).

The backend reads the *committed* model artifact JSON and builds the pure
``restart.engine.xg.XGModelBundle`` directly — no ML-framework dependency. The
adapter still depends only on the simulation core; training lives in restart_ml.
The active pointer (``models/active.json``) is the file-based stand-in for
``ml_models.is_active`` until DB pinning lands (tech-debt P4/6).
"""

from __future__ import annotations

import json
from pathlib import Path

from restart.engine.xg import XGModelBundle, XGScorer


def _models_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "models").is_dir() and (parent / "pyproject.toml").is_file():
            return parent / "models"
    return here.parents[4] / "models"


def _active_payload(models_dir: Path | None) -> tuple[str, dict[str, object]] | None:
    root = models_dir if models_dir is not None else _models_dir()
    pointer = root / "active.json"
    if not pointer.is_file():
        return None
    name = str(json.loads(pointer.read_text(encoding="utf-8"))["active"])
    payload: dict[str, object] = json.loads((root / name).read_text(encoding="utf-8"))
    return name, payload


def load_active_scorer(models_dir: Path | None = None) -> XGScorer | None:
    """Return the pinned xG bundle as an injectable scorer, or None if untrained."""
    found = _active_payload(models_dir)
    if found is None:
        return None
    _, payload = found
    bundle = payload["bundle"]
    assert isinstance(bundle, dict)
    return XGModelBundle.from_dict(bundle)


def active_model_id(models_dir: Path | None = None) -> str | None:
    """Identifier of the active bundle (its artifact stem), or None."""
    found = _active_payload(models_dir)
    if found is None:
        return None
    name, _ = found
    return name.removesuffix(".json")

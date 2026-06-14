"""xG model artifacts: the engine-loadable bundle + the active-model pin.

Artifacts are plain JSON (the pure core consumes a dict). The ``active.json``
pointer is the file-based stand-in for ``ml_models.is_active`` (DB pinning is a
drop-in later, tech-debt P4/6). ``training_data_hash`` chains a model to the
exact mart snapshot it was trained on (design doc 06 §2.4).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from restart import ENGINE_VERSION
from restart.engine.xg import XGModelBundle
from restart_etl.config import default_paths


def models_dir() -> Path:
    # Committed (not under git-ignored data/): the bundle is a small derived
    # coefficient artifact — the shippable model — and CI cannot retrain (raw
    # data is git-ignored), so the engine integration relies on it being present.
    return default_paths().root / "models"


def training_data_hash(mart_path: Path) -> str:
    return hashlib.sha256(mart_path.read_bytes()).hexdigest()


def write_bundle(
    bundle: XGModelBundle,
    *,
    metrics: dict[str, Any],
    training_data_hash: str,
    out_dir: Path | None = None,
) -> Path:
    """Write the bundle artifact and update the active pointer. Returns its path."""
    root = out_dir if out_dir is not None else models_dir()
    root.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema": "xg-bundle/1",
        "engine_version": ENGINE_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "training_data_hash": training_data_hash,
        "metrics": metrics,
        "bundle": bundle.to_dict(),
    }
    path = root / f"{bundle.bundle_id}.json"
    # Trailing newline keeps the committed artifact stable under end-of-file hooks.
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "active.json").write_text(
        json.dumps({"active": path.name}, indent=2) + "\n", encoding="utf-8"
    )
    return path


def load_active_bundle(models_root: Path | None = None) -> XGModelBundle | None:
    """Load the pinned active bundle, or None if no model has been trained."""
    root = models_root if models_root is not None else models_dir()
    pointer = root / "active.json"
    if not pointer.is_file():
        return None
    name = json.loads(pointer.read_text(encoding="utf-8"))["active"]
    payload = json.loads((root / name).read_text(encoding="utf-8"))
    return XGModelBundle.from_dict(payload["bundle"])

"""MLflow logging for studies (design doc 06 sec4): every System-B study is
logged with params, metrics, and provenance.

Mirrors the xG training package's choice of a local SQLite backend (the MLflow
file store is deprecated/maintenance-mode). Logging is best-effort: the caller
wraps it so a missing/locked tracking DB never fails a study run.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from restart import ENGINE_VERSION
from restart_opt import OPT_VERSION


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:  # pragma: no cover - git absent / not a repo
        return "unknown"


def log_study(
    document: dict[str, Any], db_path: Path | None = None, experiment: str = "optimizer"
) -> None:
    """Log one study document to MLflow (SQLite backend)."""
    import mlflow

    db = db_path if db_path is not None else Path("data") / "mlflow.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{db.as_posix()}")
    mlflow.set_experiment(experiment)

    config = document.get("config", {})
    tpe = document.get("tpe", {})
    rnd = document.get("random", {})
    confirm = document.get("confirm", [])
    with mlflow.start_run(run_name=str(document.get("name", "study"))):
        mlflow.log_param("engine_version", ENGINE_VERSION)
        mlflow.log_param("opt_version", OPT_VERSION)
        mlflow.log_param("git_sha", _git_sha())
        for k, v in config.items():
            mlflow.log_param(k, v)
        if "best_value" in tpe:
            mlflow.log_metric("tpe_best_screen_xg", float(tpe["best_value"]))
        if "best_value" in rnd:
            mlflow.log_metric("random_best_screen_xg", float(rnd["best_value"]))
        if "best_value" in tpe and "best_value" in rnd:
            mlflow.log_metric(
                "tpe_minus_random", float(tpe["best_value"]) - float(rnd["best_value"])
            )
        if confirm:
            mlflow.log_metric("best_confirmed_xg", max(float(c["mean_xg"]) for c in confirm))
        winner = document.get("winner", {})
        if "beats_baseline" in winner:
            mlflow.log_metric("winner_beats_baseline", 1.0 if winner["beats_baseline"] else 0.0)

"""xG training pipeline: method comparison, shipped fit, bundle, MLflow.

For each body-part split (header / foot): run the full candidate sweep under
grouped-by-match CV (the method-comparison deliverable, doc 06 §5), then fit and
calibrate the shipped logistic model into a pure scorer. The two scorers form the
engine bundle. Everything is logged to MLflow when enabled. The decision to ship
the logistic model (keeping the simulation core dependency-free) is recorded with
its held-out calibration evidence - GBMs are evaluated and reported, not shipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from restart import ENGINE_VERSION
from restart.engine.xg import XGModelBundle
from restart_ml import ML_VERSION
from restart_ml.artifacts import training_data_hash, write_bundle
from restart_ml.data import Dataset, default_mart_path, load_datasets
from restart_ml.evaluate import cross_val_oof
from restart_ml.fit import FittedModel, fit_logistic_scorer
from restart_ml.models import candidate_models

ProgressFn = Any  # Callable[[str], None]


def _noop(_: str) -> None:  # pragma: no cover
    pass


@dataclass(frozen=True, slots=True)
class SplitResult:
    model_id: str
    n: int
    base_rate: float
    comparison: dict[str, dict[str, float]]  # candidate -> CV metrics
    shipped: FittedModel


@dataclass(frozen=True, slots=True)
class TrainResult:
    header: SplitResult
    foot: SplitResult
    bundle_path: Path
    training_data_hash: str
    metrics: dict[str, Any] = field(default_factory=dict)


def _sweep(dataset: Dataset, n_splits: int, echo: ProgressFn) -> dict[str, dict[str, float]]:
    comparison: dict[str, dict[str, float]] = {}
    for name, factory in candidate_models().items():
        _, metrics = cross_val_oof(factory, dataset.x, dataset.y, dataset.groups, n_splits=n_splits)
        comparison[name] = metrics
        echo(
            f"  {dataset.model_id}/{name}: logloss={metrics['log_loss']:.4f} "
            f"brier={metrics['brier']:.4f} auc={metrics['auc']:.3f} "
            f"cal_slope={metrics['cal_slope']:.2f}"
        )
    return comparison


def _train_split(dataset: Dataset, n_splits: int, echo: ProgressFn) -> SplitResult:
    echo(f"{dataset.model_id}: n={dataset.n} base_rate={dataset.base_rate:.3f}")
    comparison = _sweep(dataset, n_splits, echo)
    shipped = fit_logistic_scorer(dataset, n_splits=n_splits)
    echo(
        f"  shipped logistic: cal_slope={shipped.metrics_calibrated['cal_slope']:.3f} "
        f"cal_intercept={shipped.metrics_calibrated['cal_intercept']:.3f}"
    )
    return SplitResult(
        model_id=dataset.model_id,
        n=dataset.n,
        base_rate=dataset.base_rate,
        comparison=comparison,
        shipped=shipped,
    )


def _log_mlflow(result_splits: list[SplitResult], mart_path: Path, data_hash: str) -> None:
    import mlflow

    # SQLite tracking backend (the file store is deprecated/maintenance-mode):
    # local, server-free, captures params + metrics for every run.
    db = default_mart_path().parent.parent / "mlflow.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{db.as_posix()}")
    mlflow.set_experiment("xg-v1")
    for split in result_splits:
        with mlflow.start_run(run_name=split.model_id):
            mlflow.log_param("model_id", split.model_id)
            mlflow.log_param("engine_version", ENGINE_VERSION)
            mlflow.log_param("ml_version", ML_VERSION)
            mlflow.log_param("n", split.n)
            mlflow.log_param("training_data_hash", data_hash)
            mlflow.log_metric("base_rate", split.base_rate)
            for name, metrics in split.comparison.items():
                for k, v in metrics.items():
                    if v == v:  # skip NaN
                        mlflow.log_metric(f"{name}__{k}", v)
            for k, v in split.shipped.metrics_calibrated.items():
                if v == v:
                    mlflow.log_metric(f"shipped__{k}", v)


def train_xg(
    *,
    mart_path: Path | None = None,
    out_dir: Path | None = None,
    n_splits: int = 5,
    use_mlflow: bool = True,
    progress: ProgressFn | None = None,
) -> TrainResult:
    echo = progress if progress is not None else _noop
    path = mart_path if mart_path is not None else default_mart_path()
    header_ds, foot_ds = load_datasets(path)

    header = _train_split(header_ds, n_splits, echo)
    foot = _train_split(foot_ds, n_splits, echo)

    bundle = XGModelBundle(header=header.shipped.scorer, foot=foot.shipped.scorer)
    data_hash = training_data_hash(path)
    metrics = {
        "header": header.shipped.metrics_calibrated,
        "foot": foot.shipped.metrics_calibrated,
    }
    bundle_path = write_bundle(
        bundle, metrics=metrics, training_data_hash=data_hash, out_dir=out_dir
    )
    echo(f"wrote bundle -> {bundle_path}")

    if use_mlflow:
        try:
            _log_mlflow([header, foot], path, data_hash)
            echo("logged runs to MLflow")
        except Exception as exc:  # pragma: no cover - MLflow optional at runtime
            echo(f"MLflow logging skipped: {exc}")

    return TrainResult(
        header=header,
        foot=foot,
        bundle_path=bundle_path,
        training_data_hash=data_hash,
        metrics=metrics,
    )

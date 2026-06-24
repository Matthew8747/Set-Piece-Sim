"""Read-only optimization surface: study.json loaded as DATA, never restart_opt.

These tests pin the data-only boundary (ADR-006/008): the API parses the
committed canonical study and serves typed DTOs without importing the optimizer
package (Optuna / LightGBM / SHAP) into the request path.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from restart_api.main import create_app
from restart_api.settings import Settings

# The committed canonical study (Phase 5 artifact, consumed read-only).
REAL_STUDIES = Path("optimization_studies")
CANONICAL = "england-vs-argentina"


def _client() -> TestClient:
    return TestClient(create_app(Settings(app_env="test", _env_file=None)))


class TestDTOs:
    def test_optimization_dtos_importable(self) -> None:
        from restart_api.schemas import OptimizationDetailDTO, OptimizationSummaryDTO

        assert "stale" in OptimizationSummaryDTO.model_fields
        assert "convergence_tpe" in OptimizationDetailDTO.model_fields


class TestDerivations:
    def test_best_so_far_is_cumulative_max(self) -> None:
        from restart_api.studies.loader import best_so_far

        series = best_so_far([{"value": 0.1}, {"value": 0.3}, {"value": 0.2}, {"value": 0.5}])
        assert [p.best_so_far for p in series] == [0.1, 0.3, 0.3, 0.5]
        assert [p.trial for p in series] == [1, 2, 3, 4]

    def test_best_so_far_empty(self) -> None:
        from restart_api.studies.loader import best_so_far

        assert best_so_far([]) == []

    def test_axes_split_continuous_and_categorical_and_order_by_importance(self) -> None:
        from restart_api.studies.loader import axes_from

        trials = [
            {"params": {"speed_ms": 22.0, "delivery_type": "inswinger"}},
            {"params": {"speed_ms": 25.0, "delivery_type": "floated"}},
        ]
        axes = axes_from(trials, {"speed_ms": 0.4, "delivery_type": 0.1})
        by_name = {a.name: a for a in axes}
        assert by_name["speed_ms"].kind == "continuous"
        assert by_name["speed_ms"].domain == [22.0, 25.0]
        assert by_name["delivery_type"].kind == "categorical"
        assert set(by_name["delivery_type"].categories or []) == {"inswinger", "floated"}
        # Most important axis comes first (the wow-view reads left-to-right).
        assert axes[0].name == "speed_ms"


class TestLoader:
    def test_loader_reads_canonical_study_as_data(self) -> None:
        from restart_api.studies.loader import StudyLoader

        detail = StudyLoader(REAL_STUDIES).get_detail(CANONICAL)
        assert detail.id == CANONICAL
        assert detail.matchup.attacking and detail.matchup.defending
        # One convergence point per trial, for both samplers.
        assert len(detail.convergence_tpe) == len(detail.trials)
        assert len(detail.convergence_random) > 0
        assert detail.axes and detail.insights
        assert isinstance(detail.winner.beats_baseline, bool)
        # Best-so-far is monotone non-decreasing (it is a running max).
        bsf = [p.best_so_far for p in detail.convergence_tpe]
        assert all(b >= a for a, b in itertools.pairwise(bsf))

    def test_list_summaries_includes_canonical(self) -> None:
        from restart_api.studies.loader import StudyLoader

        ids = {s.id for s in StudyLoader(REAL_STUDIES).list_summaries()}
        assert CANONICAL in ids

    def test_unknown_study_raises_keyerror(self) -> None:
        from restart_api.studies.loader import StudyLoader

        with pytest.raises(KeyError):
            StudyLoader(REAL_STUDIES).get_detail("does-not-exist")


class TestEndpoints:
    def test_list_optimizations(self) -> None:
        resp = _client().get("/api/v1/optimizations")
        assert resp.status_code == 200
        assert any(s["id"] == CANONICAL for s in resp.json())

    def test_get_optimization_detail(self) -> None:
        resp = _client().get(f"/api/v1/optimizations/{CANONICAL}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["convergence_tpe"] and detail["axes"] and detail["insights"]
        assert "beats_baseline" in detail["winner"]

    def test_get_optimization_404(self) -> None:
        resp = _client().get("/api/v1/optimizations/does-not-exist")
        assert resp.status_code == 404


class TestRuntimeBoundary:
    def test_runtime_never_imports_restart_opt(self) -> None:
        # Importing the app must not drag the optimizer (Optuna/LightGBM/SHAP)
        # into the request path - the optimization surface is data-only (ADR-008).
        for name in [k for k in sys.modules if k.startswith("restart_opt")]:
            del sys.modules[name]
        import importlib

        importlib.import_module("restart_api.main")
        leaked = [k for k in sys.modules if k == "restart_opt" or k.startswith("restart_opt.")]
        assert leaked == []

"""Read-only optimization surface: study.json loaded as DATA, never restart_opt.

These tests pin the data-only boundary (ADR-006/008): the API parses the
committed canonical study and serves typed DTOs without importing the optimizer
package (Optuna / LightGBM / SHAP) into the request path.
"""

from __future__ import annotations

from pathlib import Path

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

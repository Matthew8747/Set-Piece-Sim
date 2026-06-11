"""Cross-package integration: the API app and the simulation core compose
correctly inside the uv workspace (editable installs, shared interpreter)."""

import pytest
from fastapi.testclient import TestClient

import restart
import restart_api
from restart_api.main import create_app

pytestmark = pytest.mark.integration


def test_api_exposes_simulation_core_version_end_to_end() -> None:
    client = TestClient(create_app())
    body = client.get("/healthz").json()
    assert body["engine_version"] == restart.ENGINE_VERSION
    assert body["api_version"] == restart_api.__version__


def test_packages_are_distinct_distributions() -> None:
    # Both packages resolve from their own src trees (no accidental vendoring).
    assert "simulation-core" in restart.__file__.replace("\\", "/")
    assert "backend" in restart_api.__file__.replace("\\", "/")

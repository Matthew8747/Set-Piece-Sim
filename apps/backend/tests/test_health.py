"""Endpoint tests for the ops and v1 surfaces."""

from fastapi.testclient import TestClient

from restart import ENGINE_VERSION
from restart_api import __version__
from restart_api.main import create_app
from restart_api.settings import Settings


def make_client(settings: Settings | None = None) -> TestClient:
    return TestClient(create_app(settings))


class TestHealthz:
    def test_returns_ok_with_versions(self) -> None:
        resp = make_client().get("/healthz")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "status": "ok",
            "api_version": __version__,
            "engine_version": ENGINE_VERSION,
        }

    def test_engine_version_comes_from_simulation_core(self) -> None:
        # Guards the workspace seam: the API must report the core's truth,
        # not a copy that can drift.
        body = make_client().get("/healthz").json()
        assert body["engine_version"].startswith("sim/")


class TestReadyz:
    def test_ready_with_explicit_skipped_checks(self) -> None:
        resp = make_client().get("/readyz")
        assert resp.status_code == 200
        assert resp.json() == {
            "status": "ready",
            "checks": {"database": "skipped", "redis": "skipped"},
        }


class TestMeta:
    def test_meta_reports_injected_environment(self) -> None:
        client = make_client(Settings(app_env="test"))
        body = client.get("/api/v1/meta").json()
        assert body["environment"] == "test"
        assert body["api_version"] == __version__

    def test_unknown_route_is_404(self) -> None:
        assert make_client().get("/api/v1/nonexistent").status_code == 404


class TestAppFactory:
    def test_injected_settings_control_title(self) -> None:
        app = create_app(Settings(api_title="Custom Title"))
        assert app.title == "Custom Title"

    def test_openapi_includes_all_routes(self) -> None:
        paths = make_client().get("/openapi.json").json()["paths"]
        assert {"/healthz", "/readyz", "/api/v1/meta"} <= set(paths)

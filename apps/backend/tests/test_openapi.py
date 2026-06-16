"""OpenAPI completeness — the schema is a product feature + the codegen source
(ADR-007 d6). Every route must be documented, the error contract must be the
ProblemDetail schema, and the API-key scheme must be advertised.
"""

from restart_api.main import create_app
from restart_api.settings import Settings

_OPENAPI = create_app(Settings(app_env="test")).openapi()


def test_every_route_is_documented() -> None:
    app = create_app(Settings(app_env="test"))
    documented = set(_OPENAPI["paths"].keys())
    for route in app.routes:
        path = getattr(route, "path", None)
        # Skip the docs/openapi infrastructure routes.
        if path and path.startswith("/api"):
            assert path in documented, f"route {path} missing from OpenAPI"


def test_problem_detail_is_the_error_schema() -> None:
    schemas = _OPENAPI["components"]["schemas"]
    assert "ProblemDetail" in schemas
    # A compute endpoint documents the problem response for 422.
    mc = _OPENAPI["paths"]["/api/v1/setpieces/montecarlo"]["post"]
    ref = mc["responses"]["422"]["content"]["application/problem+json"]["schema"]["$ref"]
    assert ref.endswith("/ProblemDetail")


def test_security_scheme_advertised() -> None:
    schemes = _OPENAPI["components"].get("securitySchemes", {})
    assert schemes, "no security scheme advertised"
    assert any(s.get("in") == "header" for s in schemes.values())

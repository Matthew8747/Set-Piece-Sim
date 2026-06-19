"""RFC 9457 (problem-details) error handling for the API (ADR-007 d5).

One error contract for the whole surface: every failure becomes an
``application/problem+json`` body with ``type``/``title``/``status``/``detail``
(plus a field-level ``errors`` array for validation failures). This replaces
FastAPI's default ``{"detail": ...}`` bodies so the generated TypeScript types
and any client share a single, documented error shape.

The simulation core signals invalid-but-well-formed scenarios by raising plain
``ValueError`` (see ``restart.tactics.compile`` — "all raise ValueError on
violation"); at the API boundary those are client errors (422), not server
faults, so they are mapped explicitly rather than escaping as 500s.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"

# A stable, dereferenceable-looking type URI per problem class. Kept relative so
# it is environment-agnostic; clients switch on it, humans read ``title``.
_TYPE_BASE = "https://restart-lab.dev/problems"


def problem_response(
    status: int,
    title: str,
    detail: str,
    *,
    type_: str,
    errors: list[dict[str, object]] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": f"{_TYPE_BASE}/{type_}",
        "title": title,
        "status": status,
        "detail": detail,
    }
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM_JSON)


def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Flatten pydantic's error list into a compact, UI-friendly field array.
    errors: list[dict[str, object]] = [
        {
            "loc": list(e.get("loc", [])),
            "msg": str(e.get("msg", "")),
            "type": str(e.get("type", "")),
        }
        for e in exc.errors()
    ]
    return problem_response(
        422,
        "Request validation failed",
        "One or more fields are invalid; see 'errors' for specifics.",
        type_="validation-error",
        errors=errors,
    )


def _http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return problem_response(
        exc.status_code,
        str(exc.detail) if exc.status_code < 500 else "Server error",
        str(exc.detail),
        type_="http-error",
    )


def _value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    # Domain validation (e.g. infeasible scenario at compile time) -> client error.
    return problem_response(
        422,
        "Invalid scenario",
        str(exc),
        type_="invalid-scenario",
    )


def install_error_handlers(app: FastAPI) -> None:
    """Register the problem-details handlers on ``app`` (called in create_app)."""
    app.add_exception_handler(RequestValidationError, _validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ValueError, _value_error_handler)  # type: ignore[arg-type]

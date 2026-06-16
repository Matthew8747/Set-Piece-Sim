"""Application factory.

``create_app`` takes an optional :class:`Settings` so tests inject
configuration without touching process environment or the settings cache -
the dependency-injection seam for the whole web layer.

Run locally:
    uv run uvicorn restart_api.main:app --reload --app-dir apps/backend/src
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from restart_api import __version__
from restart_api.errors import install_error_handlers
from restart_api.ratelimit import configure as configure_rate_limits
from restart_api.ratelimit import limiter, rate_limit_handler
from restart_api.routers import health, v1
from restart_api.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings if settings is not None else get_settings()

    app = FastAPI(
        title=cfg.api_title,
        version=__version__,
        # OpenAPI/docs stay enabled in all environments for now: the API is
        # read-only and the schema is a product feature (see design doc 02 §5).
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # One error contract for the whole surface (RFC 9457 problem-details).
    install_error_handlers(app)

    # Per-IP rate limiting (slowapi). The RateLimitExceeded handler is registered
    # explicitly because that exception subclasses HTTPException and would
    # otherwise be swallowed by the generic HTTP handler above.
    configure_rate_limits(cfg)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    if settings is not None:
        # Tests injected a Settings: make route dependencies see the same one.
        app.dependency_overrides[get_settings] = lambda: cfg

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )

    app.include_router(health.router)
    app.include_router(v1.router)

    return app


app = create_app()

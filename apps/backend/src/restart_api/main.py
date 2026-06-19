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
from restart_api.jobs.queue import InProcessJobQueue
from restart_api.programs import default_executor
from restart_api.ratelimit import configure as configure_rate_limits
from restart_api.ratelimit import limiter, rate_limit_handler
from restart_api.repositories.file import SqliteScenarioRepository, SqliteSimRunRepository
from restart_api.routers import health, v1
from restart_api.schemas import ERROR_RESPONSES
from restart_api.settings import Settings, get_settings


def _configure_stores_and_queue(app: FastAPI, cfg: Settings) -> None:
    """Pick repository + job-queue adapters from settings (ADR-007 d1/d2).

    Postgres / Arq are drop-ins behind the same Protocols, used when their URLs
    are set; otherwise the server-free file + in-process defaults run.
    """
    if cfg.database_url is not None:
        from restart_api.repositories.postgres import (
            PostgresScenarioRepository,
            PostgresSimRunRepository,
        )

        dsn = cfg.database_url.get_secret_value()
        app.state.scenarios = PostgresScenarioRepository(dsn)
        app.state.sim_runs = PostgresSimRunRepository(dsn)
    else:
        app.state.scenarios = SqliteScenarioRepository(cfg.app_db_path)
        app.state.sim_runs = SqliteSimRunRepository(cfg.app_db_path)

    if cfg.redis_url is not None:
        from restart_api.jobs.arq_queue import ArqJobQueue

        app.state.job_queue = ArqJobQueue(cfg.redis_url.get_secret_value())
    else:
        app.state.job_queue = InProcessJobQueue(
            app.state.sim_runs, default_executor, cfg.max_concurrent_jobs
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings if settings is not None else get_settings()

    app = FastAPI(
        title=cfg.api_title,
        version=__version__,
        summary="Set-piece simulation, Monte Carlo, and scenario API for Restart Lab.",
        # OpenAPI/docs stay enabled in all environments: the schema is a product
        # feature and the source for the generated TS client (design doc 02 §5).
        docs_url="/docs",
        openapi_url="/openapi.json",
        servers=[{"url": "/", "description": "This deployment"}],
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

    # Stores + job queue, read off app.state by the route dependencies. The
    # file/in-process defaults keep CI server-free; Postgres + Arq drop-ins are
    # selected when their URLs are configured (ADR-007 d1/d2). Tests point
    # data_dir at a tmp dir and may swap the queue's executor.
    _configure_stores_and_queue(app, cfg)

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

    app.include_router(health.router, responses=ERROR_RESPONSES)
    app.include_router(v1.router, responses=ERROR_RESPONSES)

    return app


app = create_app()

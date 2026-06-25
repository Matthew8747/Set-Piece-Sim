"""Per-IP rate limiting (slowapi) - cost-bomb protection (doc 02 9, ADR-007 d5).

A process-wide ``limiter`` singleton (slowapi needs one to decorate routes at
import time) whose limit *values* are read from the active :class:`Settings`
through a holder set by ``create_app``. So limits stay configurable per
deployment (and per test) without the limiter itself being rebuilt:

* a generous global per-IP bucket applies to every request (``rate_limit_read``);
* a stricter bucket applies to compute-triggering POSTs (``rate_limit_write``).

Storage is in-memory by default; set ``RESTART_REDIS_URL`` to share buckets
across worker processes in production.
"""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import Response

from restart_api.errors import problem_response
from restart_api.settings import Settings

# Set by create_app to the app's Settings; the limit callables read it per
# request so values are config-driven (and overridable in tests).
_settings: Settings | None = None


def _active() -> Settings:
    return _settings if _settings is not None else Settings()


def read_limit() -> str:
    return _active().rate_limit_read


def write_limit() -> str:
    return _active().rate_limit_write


# Redis storage is opt-in (prod, multi-process); in-memory otherwise. Read from
# the raw environment at import because the singleton is built once.
_redis = os.environ.get("RESTART_REDIS_URL")

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[read_limit],  # callable -> re-evaluated each request
    storage_uri=_redis,
    enabled=True,
)


def configure(settings: Settings) -> None:
    """Point the limiter at this app's settings (called in create_app)."""
    global _settings
    _settings = settings
    limiter.enabled = settings.rate_limit_enabled


def reset_for_tests() -> None:
    """Clear rate-limit buckets so tests do not leak state into one another."""
    limiter.reset()


def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    # RateLimitExceeded is itself an HTTPException subclass, so this specific
    # handler must be registered to win over the generic HTTP handler.
    return problem_response(
        429,
        "Too Many Requests",
        f"Rate limit exceeded: {exc.detail}",
        type_="rate-limit-exceeded",
    )

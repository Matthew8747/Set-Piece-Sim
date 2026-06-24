"""Write-access control for mutating/compute endpoints (doc 02 9, ADR-007 d5).

Policy: if an API key is configured (``RESTART_API_KEY``), every write/compute
request must present a matching ``X-API-Key`` header. If no key is configured the
deployment runs in **demo mode** - writes are allowed but remain bounded by the
request schemas (n_sims caps, coordinate bounds), so the public demo can be used
without a key yet cannot be cost-bombed.

``APIKeyHeader`` is used as the dependency so the scheme is advertised in OpenAPI
(visible in ``/docs``).
"""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from restart_api.settings import Settings, get_settings

# auto_error=False: we implement the policy (demo mode vs required) ourselves.
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_write_access(
    api_key: str | None = Depends(api_key_header),
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> None:
    configured = settings.api_key
    if configured is None:
        return  # demo mode: bounded writes allowed without a key.
    if api_key is None or not secrets.compare_digest(api_key, configured.get_secret_value()):
        raise HTTPException(status_code=401, detail="Missing or invalid API key")

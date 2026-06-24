# Restart Lab API — container image for the FastAPI backend.
#
# Built from the repo root (the uv workspace root):
#   docker build -f apps/backend/Dockerfile -t restart-api .
#   docker run -p 8000:8000 restart-api
#
# Installs ONLY the backend package + its workspace dep (restart-simulation-core);
# the optimizer/ML stack (optuna/lightgbm/shap) is never pulled — restart_opt is
# not an API dependency (the guard test enforces it). The optional postgres/arq
# extras are included so the same image serves the server-free demo path AND the
# scaled Postgres + Arq/Redis path (selected at runtime by RESTART_DATABASE_URL /
# RESTART_REDIS_URL).
FROM python:3.12-slim

# uv, copied from its official distroless image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    RESTART_APP_ENV=prod \
    RESTART_DEBUG=false

WORKDIR /app
COPY . .

# Backend + simulation-core only, no dev deps, with the infra adapters available.
RUN uv sync --no-dev --package restart-backend --extra postgres --extra arq

ENV PATH="/app/.venv/bin:$PATH"

# data/ (marts + the local SQLite store) is provided at runtime via a mounted
# volume or a build step; the read-only optimization surface already works from
# the committed optimization_studies/.
EXPOSE 8000

# Liveness: the health router reports the engine build id at /healthz.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"]

CMD ["uvicorn", "restart_api.main:app", "--app-dir", "apps/backend/src", "--host", "0.0.0.0", "--port", "8000"]

# Restart Lab API

FastAPI surface for set-piece simulation, Monte Carlo, real squads, and persisted
scenarios (design doc 02; architecture in [ADR-007](../adr/ADR-007-api-workbench-and-persistence.md)).

- **Interactive docs:** `GET /docs` (Swagger UI) · machine schema: `GET /openapi.json`
  (committed at [`apps/backend/openapi.json`](../../apps/backend/openapi.json); `@restart/shared-types`
  is generated from it).
- **Base URL (dev):** `http://localhost:8000`
- **Run it:** `uv run uvicorn restart_api.main:app --app-dir apps/backend/src`

## Conventions

- **Errors** are RFC 9457 problem-details (`application/problem+json`):
  `{type, title, status, detail, errors?}`.
- **Writes** (`POST`) require `X-API-Key` **when** the deployment sets `RESTART_API_KEY`.
  With no key configured the deployment is demo-mode: bounded writes are allowed
  (e.g. `n_sims ≤ 2000`), reads are open.
- **Rate limits** are per-IP (slowapi): reads `120/min`, compute writes `20/min` by default
  (`429` + problem-json on exceed). Concurrent jobs are capped by the queue.
- **Determinism:** a sim run is keyed by the canonical scenario hash folded with `seed` +
  `engine_version`; the same key returns the existing run (never recomputed).

## Endpoints

### Ops

| Method | Path | Notes |
|---|---|---|
| GET | `/healthz` | liveness + `engine_version` |
| GET | `/readyz` | readiness; probes configured Postgres/Redis (503 if unreachable) |
| GET | `/api/v1/meta` | api/engine version + environment |

### Catalog + one-shot simulation

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/setpieces/routines` | corner routines |
| GET | `/api/v1/setpieces/schemes` | defensive schemes |
| POST | `/api/v1/setpieces/simulate` | one deterministic sim (replay payload) |
| POST | `/api/v1/setpieces/montecarlo` | synchronous Monte Carlo (bounded `n_sims`) |

### Real squads (from the marts)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/teams` | available nations (StatsBomb-derived) |
| GET | `/api/v1/players?team=<slug>` | the selected XI + attribute provenance |

### Scenarios + async sim runs

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/scenarios` | create a named spec (`201`) |
| GET | `/api/v1/scenarios` | list |
| GET | `/api/v1/scenarios/{id}` | fetch one |
| POST | `/api/v1/sim-runs` | enqueue a run (`202`), or `200` + existing on idempotency hit |
| GET | `/api/v1/sim-runs/{id}` | poll status/progress; carries the result + `xg_samples` when complete |
| GET | `/api/v1/sim-runs/{id}/events?sample=worst\|median\|best` | replay one representative sim |

## Worked example (demo mode)

```bash
BASE=http://localhost:8000

# 1. pick a routine + scheme
ROUTINE=$(curl -s $BASE/api/v1/setpieces/routines | jq -r '.[0].routine_id')
SCHEME=$(curl -s $BASE/api/v1/setpieces/schemes  | jq -r '.[0].scheme_id')

# 2. create a scenario (real squads by slug; england vs argentina are the defaults)
SCENARIO=$(curl -s -X POST $BASE/api/v1/scenarios \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"England corner\",\"routine_id\":\"$ROUTINE\",\"scheme_id\":\"$SCHEME\",
       \"attacking_team_id\":\"england\",\"defending_team_id\":\"argentina\"}" | jq -r .scenario_id)

# 3. enqueue a Monte Carlo run (202 -> a run id)
RUN=$(curl -s -X POST $BASE/api/v1/sim-runs \
  -H 'Content-Type: application/json' \
  -d "{\"scenario_id\":\"$SCENARIO\",\"n_sims\":200,\"root_seed\":7}" | jq -r .run_id)

# 4. poll until complete (status: queued -> running -> complete)
curl -s $BASE/api/v1/sim-runs/$RUN | jq '{status, progress, p_goal: .result.p_goal}'

# 5. replay the median sim
curl -s "$BASE/api/v1/sim-runs/$RUN/events?sample=median" | jq '{outcome, frames: (.track_times_s | length)}'
```

With an API key configured, add `-H "X-API-Key: $RESTART_API_KEY"` to every `POST`.

## Server-backed deployment (optional)

The default install is server-free (SQLite + in-process queue). To run against Postgres + Arq/Redis
see [`infra/docker-compose.yml`](../../infra/docker-compose.yml): set `RESTART_DATABASE_URL` /
`RESTART_REDIS_URL`, load the marts with `restart-etl load-postgres`, and start the Arq worker
(`arq restart_api.jobs.arq_queue.WorkerSettings`). The adapters are selected automatically when the
URLs are present.

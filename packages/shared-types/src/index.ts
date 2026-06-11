/**
 * API contract types, hand-mirrored from `apps/backend/src/restart_api/schemas.py`.
 *
 * KNOWN TECH DEBT (tracked in docs/development-guide.md): these are maintained
 * by hand until the API surface is large enough to justify OpenAPI codegen
 * (planned alongside Phase 6, when the real domain endpoints land). Until
 * then, the backend's `test_openapi_includes_all_routes` plus PR review keep
 * the two sides honest.
 */

export interface HealthResponse {
  status: "ok";
  api_version: string;
  engine_version: string;
}

export interface ReadyResponse {
  status: "ready";
  checks: Record<string, "ok" | "skipped">;
}

export interface MetaResponse {
  api_version: string;
  engine_version: string;
  environment: "dev" | "test" | "prod";
}

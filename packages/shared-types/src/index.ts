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

// --- Set-piece MVP (Phase 3) ------------------------------------------------

export interface RoutineSummary {
  routine_id: string;
  name: string;
  set_piece: string;
}

export interface SchemeSummary {
  scheme_id: string;
  name: string;
}

export interface EventDTO {
  kind: string;
  time_s: number;
  player_id: string | null;
  team: string | null;
}

export interface SimulateRequest {
  routine_id: string;
  scheme_id: string;
  seed?: number;
}

/** att_tracks / def_tracks are [tick][player][x,y]; ball_path is [sample][x,y,z]. */
export interface SimulateResponse {
  engine_version: string;
  seed: number;
  outcome: string;
  events: EventDTO[];
  track_times_s: number[];
  att_tracks: number[][][];
  def_tracks: number[][][];
  ball_path: number[][];
}

export interface ProportionCI {
  p: number;
  lo: number;
  hi: number;
  k: number;
  n: number;
}

export interface MonteCarloRequest {
  routine_id: string;
  scheme_id: string;
  n_sims?: number;
  root_seed?: number;
}

export interface MonteCarloResponse {
  engine_version: string;
  root_seed: number;
  n_sims: number;
  p_goal: ProportionCI;
  p_shot: ProportionCI;
  p_header_shot: ProportionCI;
  p_first_contact_attack: ProportionCI;
  p_clearance: ProportionCI;
  p_possession_recovered: ProportionCI;
  outcome_counts: Record<string, number>;
}

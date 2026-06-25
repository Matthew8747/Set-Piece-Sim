import type {
  MonteCarloRequest,
  MonteCarloResponse,
  OptimizationDetail,
  OptimizationSummary,
  PlayerDTO,
  ProblemDetail,
  RoutineSummary,
  ScenarioCreate,
  ScenarioDTO,
  SchemeSummary,
  SimRunCreate,
  SimRunStatus,
  SimulateRequest,
  SimulateResponse,
  TeamSummary,
} from "@restart/shared-types";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
// Writes are gated by X-API-Key when the deployment configures one; in demo
// mode it is unset and bounded writes are allowed (ADR-007 d5).
const API_KEY = process.env.NEXT_PUBLIC_API_KEY;

/** Surface RFC 9457 problem-details as a readable error (ADR-007 d5). */
async function fail(res: Response, method: string, path: string): Promise<never> {
  let detail = `${res.status}`;
  try {
    const body = (await res.json()) as Partial<ProblemDetail>;
    if (body.title || body.detail) detail = `${body.title ?? res.status}: ${body.detail ?? ""}`;
  } catch {
    /* non-JSON error body - keep the status code */
  }
  throw new Error(`${method} ${path} → ${detail}`);
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) await fail(res, "GET", path);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown, write = false): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (write && API_KEY) headers["X-API-Key"] = API_KEY;
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) await fail(res, "POST", path);
  return res.json() as Promise<T>;
}

const TERMINAL = new Set(["complete", "failed"]);

export const api = {
  // Set-piece catalog + one-shot simulation (Phase 3 surface).
  routines: () => get<RoutineSummary[]>("/api/v1/setpieces/routines"),
  schemes: () => get<SchemeSummary[]>("/api/v1/setpieces/schemes"),
  simulate: (req: SimulateRequest) =>
    post<SimulateResponse>("/api/v1/setpieces/simulate", req, true),
  montecarlo: (req: MonteCarloRequest) =>
    post<MonteCarloResponse>("/api/v1/setpieces/montecarlo", req, true),

  // Real squads from the marts (ADR-007 d2).
  teams: () => get<TeamSummary[]>("/api/v1/teams"),
  players: (team: string) => get<PlayerDTO[]>(`/api/v1/players?team=${encodeURIComponent(team)}`),

  // Scenario persistence.
  scenarios: () => get<ScenarioDTO[]>("/api/v1/scenarios"),
  scenario: (id: string) => get<ScenarioDTO>(`/api/v1/scenarios/${id}`),
  createScenario: (body: ScenarioCreate) => post<ScenarioDTO>("/api/v1/scenarios", body, true),

  // Async sim runs (ADR-007 d3): POST enqueues, GET polls, /events replays one sim.
  createSimRun: (body: SimRunCreate) => post<SimRunStatus>("/api/v1/sim-runs", body, true),
  getSimRun: (id: string) => get<SimRunStatus>(`/api/v1/sim-runs/${id}`),
  simRunEvents: (id: string, sample: "worst" | "median" | "best" = "median") =>
    get<SimulateResponse>(`/api/v1/sim-runs/${id}/events?sample=${sample}`),

  // Read-only optimization studies (ADR-008): persisted study.json as data.
  optimizations: () => get<OptimizationSummary[]>("/api/v1/optimizations"),
  optimization: (id: string) =>
    get<OptimizationDetail>(`/api/v1/optimizations/${encodeURIComponent(id)}`),

  /**
   * Poll a sim run to a terminal state (the single progress seam - polling, not
   * SSE, per ADR-007 d4). Calls onProgress on each tick; resolves with the final
   * status; rejects if the run fails or the deadline passes.
   */
  async pollSimRun(
    id: string,
    onProgress?: (status: SimRunStatus) => void,
    intervalMs = 400,
    timeoutMs = 120_000,
  ): Promise<SimRunStatus> {
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      const status = await this.getSimRun(id);
      onProgress?.(status);
      if (TERMINAL.has(status.status)) {
        if (status.status === "failed") {
          // The backend stores RFC-style {type, detail} on a failed run.
          throw new Error(`sim run ${id} failed: ${status.error?.detail ?? "unknown error"}`);
        }
        return status;
      }
      if (Date.now() > deadline) throw new Error(`sim run ${id} timed out`);
      await new Promise((r) => setTimeout(r, intervalMs));
    }
  },
};

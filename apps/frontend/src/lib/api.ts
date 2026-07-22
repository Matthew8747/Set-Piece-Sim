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

export const API_BASE_URL = BASE;

/**
 * A failed `fetch` (DNS, connection refused, CORS, TLS) rejects with a
 * TypeError, distinct from an HTTP error the server actually returned. The
 * status banner uses this to tell "the backend isn't reachable" (asleep / not
 * deployed) apart from "the backend answered with an error".
 */
export function isNetworkError(e: unknown): boolean {
  return e instanceof TypeError;
}

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
  /**
   * Liveness probe for the status banner. Resolves true when the backend
   * answers, false on any network failure or non-200. `timeoutMs` bounds a
   * cold-start wait so a sleeping Fly machine doesn't hang the check forever;
   * the banner distinguishes "still waking" from "unreachable".
   */
  async health(timeoutMs = 6000): Promise<boolean> {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), timeoutMs);
    try {
      const res = await fetch(`${BASE}/healthz`, { signal: ctl.signal });
      return res.ok;
    } catch {
      return false;
    } finally {
      clearTimeout(timer);
    }
  },

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
   * status; rejects if the run fails or stops making progress.
   *
   * The deadline is on *stalled* time, not total time. A fixed total budget gets
   * the trade-off backwards: a large batch on a slow host is healthy but slow,
   * and a wedged job is fast to detect - the old flat 120 s killed legitimate
   * 500-2000 sim runs while still waiting two minutes on a genuinely stuck one.
   * `stallMs` restarts on every observed progress tick; `maxMs` is a backstop.
   */
  async pollSimRun(
    id: string,
    onProgress?: (status: SimRunStatus) => void,
    intervalMs = 400,
    stallMs = 90_000,
    maxMs = 900_000,
  ): Promise<SimRunStatus> {
    const start = Date.now();
    let lastProgress = -1;
    let lastMovedAt = Date.now();
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
      if (status.progress !== lastProgress) {
        lastProgress = status.progress;
        lastMovedAt = Date.now();
      }
      if (Date.now() - lastMovedAt > stallMs) {
        throw new Error(
          `sim run ${id} stalled at ${Math.round(lastProgress * 100)}% for ${Math.round(stallMs / 1000)}s`,
        );
      }
      if (Date.now() - start > maxMs) throw new Error(`sim run ${id} exceeded ${maxMs / 1000}s`);
      await new Promise((r) => setTimeout(r, intervalMs));
    }
  },
};

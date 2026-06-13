import type {
  MonteCarloRequest,
  MonteCarloResponse,
  RoutineSummary,
  SchemeSummary,
  SimulateRequest,
  SimulateResponse,
} from "@restart/shared-types";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  routines: () => get<RoutineSummary[]>("/api/v1/setpieces/routines"),
  schemes: () => get<SchemeSummary[]>("/api/v1/setpieces/schemes"),
  simulate: (req: SimulateRequest) => post<SimulateResponse>("/api/v1/setpieces/simulate", req),
  montecarlo: (req: MonteCarloRequest) =>
    post<MonteCarloResponse>("/api/v1/setpieces/montecarlo", req),
};

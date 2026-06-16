/**
 * API contract types for the frontend.
 *
 * These are now GENERATED from the backend's OpenAPI schema (ADR-007 d6): the
 * source of truth is `apps/backend/openapi.json`, regenerated into
 * `generated.ts` via `npm run gen -w @restart/shared-types`. CI fails on drift
 * (scripts/verify.ps1), so the hand-mirroring tech-debt is retired.
 *
 * This module re-exports stable, curated aliases over the generated schemas so
 * call sites keep using short names (e.g. `MonteCarloResponse`) instead of
 * `components["schemas"][...]`.
 */

import type { components } from "./generated";

export type { components, paths, operations } from "./generated";

type Schemas = components["schemas"];

// Ops / meta
export type HealthResponse = Schemas["HealthResponse"];
export type ReadyResponse = Schemas["ReadyResponse"];
export type MetaResponse = Schemas["MetaResponse"];
export type ProblemDetail = Schemas["ProblemDetail"];

// Set-piece catalog + simulation
export type RoutineSummary = Schemas["RoutineSummary"];
export type SchemeSummary = Schemas["SchemeSummary"];
export type EventDTO = Schemas["EventDTO"];
export type SimulateRequest = Schemas["SimulateRequest"];
export type SimulateResponse = Schemas["SimulateResponse"];
export type ProportionCI = Schemas["ProportionCIDTO"];
export type MonteCarloRequest = Schemas["MonteCarloRequest"];
export type MonteCarloResponse = Schemas["MonteCarloResponse"];

// Teams + players (real squads from the marts)
export type TeamSummary = Schemas["TeamSummaryDTO"];
export type PlayerDTO = Schemas["PlayerDTO"];

// Scenario persistence + async sim runs
export type ScenarioCreate = Schemas["ScenarioCreate"];
export type ScenarioDTO = Schemas["ScenarioDTO"];
export type SimRunCreate = Schemas["SimRunCreate"];
export type SimRunResult = Schemas["SimRunResultDTO"];
export type SimRunStatus = Schemas["SimRunStatusDTO"];

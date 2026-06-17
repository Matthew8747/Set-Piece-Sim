"use client";

import type {
  RoutineSummary,
  ScenarioDTO,
  SchemeSummary,
  TeamSummary,
} from "@restart/shared-types";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";

import { BuildPanel } from "./BuildPanel";
import { ReplayPanel } from "./ReplayPanel";
import { SimulatePanel } from "./SimulatePanel";

type Mode = "build" | "simulate" | "replay";
const MODES: { mode: Mode; key: string; label: string }[] = [
  { mode: "build", key: "B", label: "Build" },
  { mode: "simulate", key: "S", label: "Simulate" },
  { mode: "replay", key: "R", label: "Replay" },
];

export function ScenarioWorkbench({ scenarioId }: { scenarioId: string }) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("build");
  const [scenario, setScenario] = useState<ScenarioDTO | null>(null);
  const [routines, setRoutines] = useState<RoutineSummary[]>([]);
  const [schemes, setSchemes] = useState<SchemeSummary[]>([]);
  const [teams, setTeams] = useState<TeamSummary[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.scenario(scenarioId), api.routines(), api.schemes(), api.teams()])
      .then(([sc, r, s, t]) => {
        setScenario(sc);
        setRoutines(r);
        setSchemes(s);
        setTeams(t);
      })
      .catch((e: unknown) => setError(String(e)));
  }, [scenarioId]);

  // Keyboard: B/S/R switch modes (doc 07 §4). Ignore while typing in a field.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement | null;
      if (el && (/^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName) || el.isContentEditable)) return;
      const hit = MODES.find((m) => m.key.toLowerCase() === e.key.toLowerCase());
      if (hit) {
        e.preventDefault();
        setMode(hit.mode);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const onSaved = useCallback(
    (newId: string) => {
      if (newId === scenarioId) return;
      router.push(`/scenarios/${newId}`);
    },
    [router, scenarioId],
  );

  if (error) return <p className="font-mono text-sm text-(--color-warn)">{error}</p>;
  if (!scenario) return <p className="font-mono text-sm opacity-50">loading scenario…</p>;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">{scenario.name}</h1>
        <nav className="flex gap-1" aria-label="Workbench mode">
          {MODES.map((m) => (
            <button
              key={m.mode}
              type="button"
              onClick={() => setMode(m.mode)}
              aria-pressed={mode === m.mode}
              className={`rounded px-3 py-1.5 text-sm ${
                mode === m.mode
                  ? "bg-(--color-signal) font-medium text-black"
                  : "border border-(--color-line)/20 opacity-70"
              }`}
            >
              {m.label} <span className="font-mono text-xs opacity-50">{m.key}</span>
            </button>
          ))}
        </nav>
      </header>

      {mode === "build" && (
        <BuildPanel
          routines={routines}
          schemes={schemes}
          teams={teams}
          initial={{
            routineId: scenario.spec.routine_id ?? routines[0]?.routine_id ?? "",
            schemeId: scenario.spec.scheme_id ?? schemes[0]?.scheme_id ?? "",
            attId: scenario.spec.attacking_team_id ?? teams[0]?.team_id ?? "",
            defId: scenario.spec.defending_team_id ?? teams[0]?.team_id ?? "",
          }}
          onSaved={onSaved}
        />
      )}
      {mode === "simulate" && (
        // Stay on Simulate so the distributions render; the completed run is held
        // so Replay (press R) can pull its representative trajectories.
        <SimulatePanel scenarioId={scenarioId} onComplete={(id) => setRunId(id)} />
      )}
      {mode === "replay" && <ReplayPanel runId={runId} />}
    </div>
  );
}

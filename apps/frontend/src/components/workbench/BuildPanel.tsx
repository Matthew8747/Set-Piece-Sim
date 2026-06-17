"use client";

import type { PlayerDTO, RoutineSummary, SchemeSummary, TeamSummary } from "@restart/shared-types";
import {
  GOAL_LINE_X,
  HALF_WIDTH,
  PITCH_H,
  PITCH_W,
  PX_PER_M,
  Pitch,
  screenX,
  screenY,
  snap,
} from "@restart/pitch-kit";
import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";

export interface BuildPanelProps {
  routines: RoutineSummary[];
  schemes: SchemeSummary[];
  teams: TeamSummary[];
  initial: { routineId: string; schemeId: string; attId: string; defId: string };
  onSaved: (scenarioId: string) => void;
}

// Planning aids only: the scenario spec the engine simulates is the picked
// routine/scheme + squads (the backend has no per-point geometry by design).
// These handles let an analyst annotate intended delivery + run, snapped to the
// 0.5 m grid, with live kinematic feasibility (doc 07 §3) as a teaching cue.
const CORNER = { x: GOAL_LINE_X, y: HALF_WIDTH }; // ball starts at the corner flag
const BALL_SPEED = 18; // m/s, indicative inswinger
const RUNNER_SPEED = 7; // m/s, sprinting attacker

type Pt = { x: number; y: number };

function dist(a: Pt, b: Pt): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

export function BuildPanel({ routines, schemes, teams, initial, onSaved }: BuildPanelProps) {
  const [routineId, setRoutineId] = useState(initial.routineId);
  const [schemeId, setSchemeId] = useState(initial.schemeId);
  const [attId, setAttId] = useState(initial.attId);
  const [defId, setDefId] = useState(initial.defId);
  const [players, setPlayers] = useState<PlayerDTO[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Local-only planning handles (world metres).
  const [delivery, setDelivery] = useState<Pt>({ x: 45, y: 3 });
  const [runnerZone, setRunnerZone] = useState<Pt>({ x: 49, y: 0 });
  const dragging = useRef<"delivery" | "runner" | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!attId) return;
    api
      .players(attId)
      .then(setPlayers)
      .catch((e: unknown) => setError(String(e)));
  }, [attId]);

  function clientToWorld(clientX: number, clientY: number): Pt {
    const svg = wrapRef.current?.querySelector("svg");
    if (!svg) return { x: 0, y: 0 };
    const rect = svg.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return { x: 0, y: 0 };
    const px = ((clientX - rect.left) / rect.width) * (PITCH_W + 12) - 6;
    const py = ((clientY - rect.top) / rect.height) * (PITCH_H + 12) - 6;
    return { x: snap(GOAL_LINE_X - py / PX_PER_M), y: snap(px / PX_PER_M - HALF_WIDTH) };
  }

  function onMove(e: React.PointerEvent) {
    if (!dragging.current) return;
    const p = clientToWorld(e.clientX, e.clientY);
    if (dragging.current === "delivery") setDelivery(p);
    else setRunnerZone(p);
  }

  // Can the runner reach the delivery point before the ball arrives?
  const flightTime = dist(CORNER, delivery) / BALL_SPEED;
  const runDist = dist(runnerZone, delivery);
  const feasible = runDist <= RUNNER_SPEED * flightTime + 0.5;

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const team = teams.find((t) => t.team_id === attId);
      const created = await api.createScenario({
        name: `${team?.name ?? attId} — ${routines.find((r) => r.routine_id === routineId)?.name ?? routineId}`,
        routine_id: routineId,
        scheme_id: schemeId,
        attacking_team_id: attId,
        defending_team_id: defId,
      });
      onSaved(created.scenario_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <section className="flex flex-col gap-4">
        <Picker label="Attacking squad" value={attId} onChange={setAttId}>
          {teams.map((t) => (
            <option key={t.team_id} value={t.team_id}>
              {t.name}
            </option>
          ))}
        </Picker>
        <Picker label="Defending squad" value={defId} onChange={setDefId}>
          {teams.map((t) => (
            <option key={t.team_id} value={t.team_id}>
              {t.name}
            </option>
          ))}
        </Picker>
        <Picker label="Routine" value={routineId} onChange={setRoutineId}>
          {routines.map((r) => (
            <option key={r.routine_id} value={r.routine_id}>
              {r.name}
            </option>
          ))}
        </Picker>
        <Picker label="Defensive scheme" value={schemeId} onChange={setSchemeId}>
          {schemes.map((s) => (
            <option key={s.scheme_id} value={s.scheme_id}>
              {s.name}
            </option>
          ))}
        </Picker>

        <button
          type="button"
          onClick={save}
          disabled={busy || !routineId || !schemeId || !attId || !defId}
          className="rounded bg-(--color-signal) px-3 py-2 font-medium text-black disabled:opacity-40"
        >
          {busy ? "saving…" : "Save as new scenario"}
        </button>
        {error && <p className="font-mono text-xs text-(--color-warn)">{error}</p>}

        {players.length > 0 && (
          <details className="text-xs">
            <summary className="cursor-pointer opacity-60">
              Selected XI ({players.length}) — provenance
            </summary>
            <ul className="mt-2 flex flex-col gap-1 font-mono opacity-70">
              {players.map((p) => (
                <li key={p.player_id} className="flex justify-between">
                  <span>{p.display_name}</span>
                  <span className="opacity-50">{p.position_group}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <div
          ref={wrapRef}
          onPointerMove={onMove}
          onPointerUp={() => (dragging.current = null)}
          onPointerLeave={() => (dragging.current = null)}
        >
          <Pitch
            ariaLabel="Build planning overlay"
            overlay={
              <PlanningOverlay
                delivery={delivery}
                runnerZone={runnerZone}
                feasible={feasible}
                onGrab={(which) => (dragging.current = which)}
              />
            }
          />
        </div>
        <p className="text-xs opacity-50">
          Planning overlay — the engine simulates the selected routine. Handles snap to 0.5 m;{" "}
          <span className={feasible ? "text-(--color-signal)" : "text-(--color-danger)"}>
            {feasible ? "run is reachable" : "run is too far to arrive in time"}
          </span>
          .
        </p>
      </section>
    </div>
  );
}

function Picker({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-(--color-line)/20 bg-(--color-surface-raised) px-2 py-1.5"
      >
        {children}
      </select>
    </label>
  );
}

function PlanningOverlay({
  delivery,
  runnerZone,
  feasible,
  onGrab,
}: {
  delivery: Pt;
  runnerZone: Pt;
  feasible: boolean;
  onGrab: (which: "delivery" | "runner") => void;
}) {
  const runColor = feasible ? "var(--color-signal)" : "var(--color-danger)";
  return (
    <g>
      <line
        x1={screenX(runnerZone.y)}
        y1={screenY(runnerZone.x)}
        x2={screenX(delivery.y)}
        y2={screenY(delivery.x)}
        stroke={runColor}
        strokeWidth={2}
        strokeDasharray="4 2"
      />
      <circle
        data-handle="runner"
        cx={screenX(runnerZone.y)}
        cy={screenY(runnerZone.x)}
        r={6}
        fill="none"
        stroke="var(--color-line)"
        strokeWidth={2}
        style={{ cursor: "grab" }}
        onPointerDown={() => onGrab("runner")}
      />
      <circle
        data-handle="delivery"
        cx={screenX(delivery.y)}
        cy={screenY(delivery.x)}
        r={6}
        fill="var(--color-signal)"
        fillOpacity={0.8}
        style={{ cursor: "grab" }}
        onPointerDown={() => onGrab("delivery")}
      />
    </g>
  );
}

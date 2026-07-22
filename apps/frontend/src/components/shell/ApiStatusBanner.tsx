"use client";

import { useEffect, useState } from "react";

import { api, API_BASE_URL } from "@/lib/api";

// The backend is a separate service (FastAPI on Fly.io) from this frontend
// (Vercel). On the demo tier the API machine scales to zero when idle, so the
// first request after a quiet spell wakes it and takes a few seconds - and if
// the backend was never deployed, calls fail outright. Without this, either case
// surfaces to a visitor as "TypeError: Failed to fetch" or a long hang that
// reads as "the site is just slow". This banner names what is actually
// happening: waking, or not reachable.

type Status = "checking" | "ok" | "waking" | "down";

// Localhost default means no backend URL was configured at build time - i.e. a
// production deploy that never set NEXT_PUBLIC_API_BASE_URL. Worth calling out,
// because it fails the same way a sleeping backend does but the fix is different.
const IS_LOCAL_DEFAULT = /^https?:\/\/localhost(:\d+)?$/.test(API_BASE_URL);

export function ApiStatusBanner() {
  const [status, setStatus] = useState<Status>("checking");
  // Bumped by Retry to re-run the probe effect (a user event driving a re-fetch,
  // rather than calling setState from inside the effect body).
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    // Two-stage liveness probe. State is only ever set inside the promise
    // callbacks - never synchronously in the effect body - which is the
    // codebase's fetch-in-effect idiom. A quick check first; on failure the
    // machine may be cold-starting, so a longer attempt shows "waking" before we
    // declare it unreachable.
    let live = true;
    void api.health(6000).then((ok) => {
      if (!live) return;
      if (ok) return setStatus("ok");
      setStatus("waking");
      void api.health(25000).then((ok2) => {
        if (live) setStatus(ok2 ? "ok" : "down");
      });
    });
    return () => {
      live = false;
    };
  }, [attempt]);

  if (status === "ok" || status === "checking") return null;

  const waking = status === "waking";
  return (
    <div
      role="status"
      className={`flex flex-wrap items-center gap-x-3 gap-y-1 border-b px-4 py-2 text-xs ${
        waking
          ? "border-(--color-signal)/20 bg-(--color-signal)/10 text-(--color-line)"
          : "border-(--color-warn)/30 bg-(--color-warn)/10 text-(--color-line)"
      }`}
    >
      <span
        aria-hidden
        className={`size-1.5 shrink-0 rounded-full ${
          waking ? "animate-pulse bg-(--color-signal)" : "bg-(--color-warn)"
        }`}
      />
      {waking ? (
        <span>
          <strong className="font-medium">Waking the backend.</strong> The simulation API sleeps
          when idle to keep this demo free; the first request can take 10–30 seconds. It is not the
          site being slow.
        </span>
      ) : (
        <span>
          <strong className="font-medium">The simulation backend isn’t reachable.</strong>{" "}
          {IS_LOCAL_DEFAULT
            ? "This deploy has no API URL configured, so it’s pointing at localhost."
            : "It runs as a separate service (Fly.io) that may be asleep or offline."}{" "}
          Squads, simulations and studies all load from it, so those pages stay empty until it’s up.
        </span>
      )}
      {!waking && (
        <button
          type="button"
          onClick={() => {
            setStatus("waking");
            setAttempt((a) => a + 1);
          }}
          className="rounded border border-(--color-line)/20 px-2 py-0.5 font-mono text-[11px] transition-colors hover:bg-(--color-line)/5"
        >
          Retry
        </button>
      )}
    </div>
  );
}

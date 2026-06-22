"use client";

import type { OptimizationDetail } from "@restart/shared-types";

// Honesty surface for the ±10% attribute-sensitivity verdict (doc 09 §8, R9).
// When the top-k ranking flips under perturbation, the discovery is reported as
// a routine *class*, never a player-precise prescription — the UI says so out
// loud rather than letting the reader over-trust a single "winner".

export interface SensitivityBannerProps {
  sensitivity: OptimizationDetail["sensitivity"];
}

export function SensitivityBanner({ sensitivity }: SensitivityBannerProps) {
  if (sensitivity.rankings_flip) {
    return (
      <p
        data-testid="sensitivity-banner"
        data-flip="true"
        className="rounded border border-(--color-warn)/30 bg-(--color-warn)/10 px-3 py-2 text-xs"
      >
        <span className="font-medium text-(--color-warn)">Reporting routine classes.</span> Top-k
        order flips under ±10% attribute perturbation
        {sensitivity.flipped.length > 0 ? ` (${sensitivity.flipped.join(", ")})` : ""} — read this
        as a routine class (e.g. &ldquo;near-post inswingers beat this zonal line&rdquo;), not a
        player-precise prescription.
      </p>
    );
  }
  return (
    <p
      data-testid="sensitivity-banner"
      data-flip="false"
      className="rounded border border-(--color-signal)/20 px-3 py-2 text-xs opacity-70"
    >
      <span className="font-medium text-(--color-signal)">Routine-precise.</span> The best routine
      stays best under every ±10% attribute perturbation.
    </p>
  );
}

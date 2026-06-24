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
        className="flex items-start gap-2 rounded-lg border border-(--color-warn)/30 bg-(--color-warn)/[0.08] px-4 py-3 text-xs leading-relaxed"
      >
        <span aria-hidden className="mt-px text-(--color-warn)">
          ⚠
        </span>
        <span>
          <span className="font-medium text-(--color-warn)">Reporting routine classes.</span> Top-k
          order flips under ±10% attribute perturbation
          {sensitivity.flipped.length > 0 ? ` (${sensitivity.flipped.join(", ")})` : ""}. Read this
          as a routine class (e.g. &ldquo;near-post inswingers beat this zonal line&rdquo;), not a
          player-precise prescription.
        </span>
      </p>
    );
  }
  return (
    <p
      data-testid="sensitivity-banner"
      data-flip="false"
      className="flex items-center gap-2 rounded-lg border border-(--color-signal)/20 bg-(--color-signal)/[0.04] px-4 py-3 text-xs text-(--color-line)/75"
    >
      <span aria-hidden className="text-(--color-signal)">
        ✓
      </span>
      <span>
        <span className="font-medium text-(--color-signal)">Routine-precise.</span> The best routine
        stays best under every ±10% attribute perturbation.
      </span>
    </p>
  );
}

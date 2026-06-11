import type { MetaResponse } from "@restart/shared-types";

/**
 * Small presentational component, mostly here to prove the workspace seam:
 * it consumes the API contract type from @restart/shared-types, so a contract
 * drift breaks `tsc` rather than production.
 */
export function EnvironmentBadge({ environment }: { environment: MetaResponse["environment"] }) {
  return (
    <span className="rounded-full border border-(--color-signal)/40 px-3 py-1 font-mono text-xs tracking-widest text-(--color-signal) uppercase">
      {environment}
    </span>
  );
}

"use client";

export interface KpiCardProps {
  label: string;
  /** Point estimate (proportion in [0,1]). */
  p: number;
  /** CI bounds (proportion in [0,1]). */
  lo: number;
  hi: number;
  /** Successes / trials, surfaced for the analyst persona (doc 07 §4). */
  k?: number;
  n?: number;
  /** Plain-language method for the "how?" popover (doc 07: every number is explained). */
  howText?: string;
  modelCardHref?: string;
}

const W = 100;
const H = 14;

export function KpiCard({ label, p, lo, hi, k, n, howText, modelCardHref }: KpiCardProps) {
  const pct = (p * 100).toFixed(1);
  const half = (((hi - lo) / 2) * 100).toFixed(1);
  // Whisker domain is the CI itself; the marker sits at p within it (centre when
  // the interval has collapsed). Never imply precision the CI doesn't support.
  const span = hi - lo;
  const markerX = span > 0 ? ((p - lo) / span) * W : W / 2;

  return (
    <div className="flex flex-col gap-1 rounded-lg border border-(--color-line)/15 p-3">
      <span className="text-xs opacity-70">{label}</span>
      <span className="font-mono text-xl tabular-nums text-(--color-signal)">
        {pct}%<span className="ml-1 text-sm opacity-60">±{half}</span>
      </span>

      <svg
        data-chart="whisker"
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={`${label} confidence interval`}
      >
        <line x1={0} y1={H / 2} x2={W} y2={H / 2} stroke="var(--color-ci)" strokeWidth={1.5} />
        <line x1={0} y1={2} x2={0} y2={H - 2} stroke="var(--color-ci)" strokeWidth={1.5} />
        <line x1={W} y1={2} x2={W} y2={H - 2} stroke="var(--color-ci)" strokeWidth={1.5} />
        <circle cx={markerX} cy={H / 2} r={3} fill="var(--color-signal)" />
      </svg>

      <details className="text-xs opacity-70">
        <summary className="cursor-pointer select-none">how?</summary>
        <div className="mt-1 flex flex-col gap-1">
          <p>
            {howText ?? "Proportion with a Wilson score interval over the Monte Carlo samples."}
          </p>
          {(k !== undefined || n !== undefined) && (
            <p className="font-mono tabular-nums opacity-60">
              {k ?? "-"} / {n ?? "-"} sims
            </p>
          )}
          {modelCardHref && (
            <a href={modelCardHref} className="text-(--color-signal) underline">
              model card →
            </a>
          )}
        </div>
      </details>
    </div>
  );
}

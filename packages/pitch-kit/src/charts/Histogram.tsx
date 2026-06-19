"use client";

export interface HistogramProps {
  /** The per-sim sample array (e.g. xG per simulation). */
  samples: readonly number[];
  /** Bin count; defaults to a Freedman-ish sqrt rule, capped. */
  bins?: number;
  width?: number;
  height?: number;
  label?: string;
  color?: string;
}

function binCounts(samples: readonly number[], bins: number): { counts: number[]; max: number } {
  const counts = new Array<number>(bins).fill(0);
  let min = Infinity;
  let max = -Infinity;
  for (const v of samples) {
    if (v < min) min = v;
    if (v > max) max = v;
  }
  const span = max - min || 1;
  for (const v of samples) {
    const idx = Math.min(bins - 1, Math.floor(((v - min) / span) * bins));
    counts[idx] = (counts[idx] ?? 0) + 1;
  }
  return { counts, max: Math.max(...counts, 1) };
}

export function Histogram({
  samples,
  bins,
  width = 280,
  height = 120,
  label = "distribution",
  color = "var(--color-signal)",
}: HistogramProps) {
  if (samples.length === 0) {
    return (
      <p role="note" className="font-mono text-xs opacity-50">
        no samples yet — run a simulation
      </p>
    );
  }

  const nBins = bins ?? Math.min(30, Math.max(5, Math.round(Math.sqrt(samples.length))));
  const { counts, max } = binCounts(samples, nBins);
  const bw = width / nBins;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      role="img"
      aria-label={`Histogram of ${label}`}
    >
      {counts.map((c, i) => {
        if (c === 0) return null;
        const h = (c / max) * (height - 4);
        return (
          <rect
            key={i}
            data-chart="bar"
            x={i * bw + 0.5}
            y={height - h}
            width={Math.max(1, bw - 1)}
            height={h}
            fill={color}
            fillOpacity={0.7}
          />
        );
      })}
    </svg>
  );
}

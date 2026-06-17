"use client";

export interface EcdfProps {
  /** The per-sim sample array; the empirical CDF is drawn as a step line. */
  samples: readonly number[];
  width?: number;
  height?: number;
  label?: string;
  color?: string;
}

export function Ecdf({
  samples,
  width = 280,
  height = 120,
  label = "distribution",
  color = "var(--color-signal)",
}: EcdfProps) {
  if (samples.length === 0) {
    return (
      <p role="note" className="font-mono text-xs opacity-50">
        no samples yet — run a simulation
      </p>
    );
  }

  const sorted = [...samples].sort((a, b) => a - b);
  const min = sorted[0] ?? 0;
  const max = sorted[sorted.length - 1] ?? 1;
  const span = max - min || 1;
  const n = sorted.length;

  // Build a step polyline: each sample lifts the cumulative fraction by 1/n.
  const pts: string[] = [`0,${height}`];
  sorted.forEach((v, i) => {
    const x = ((v - min) / span) * width;
    const yBefore = height - (i / n) * height;
    const yAfter = height - ((i + 1) / n) * height;
    pts.push(`${x.toFixed(1)},${yBefore.toFixed(1)}`);
    pts.push(`${x.toFixed(1)},${yAfter.toFixed(1)}`);
  });
  pts.push(`${width},0`);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      role="img"
      aria-label={`Empirical CDF of ${label}`}
    >
      <polyline
        data-chart="ecdf"
        points={pts.join(" ")}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
      />
    </svg>
  );
}

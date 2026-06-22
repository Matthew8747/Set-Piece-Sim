"use client";

// Best-so-far convergence: the optimizer's running-max mean xG vs trial, with
// the equal-budget random baseline overlaid (random search is the honest bar,
// doc 09 §5) and the library-baseline routine drawn as a reference line. The
// winner's confirm CI is a shaded band so "beats baseline" is read, not asserted.

export interface ConvergencePoint {
  trial: number;
  bestSoFar: number;
}

export interface ConvergencePlotProps {
  tpe: readonly ConvergencePoint[];
  random: readonly ConvergencePoint[];
  /** Library baseline routine: mean + 95% CI (drawn as a reference line). */
  baseline: { mean: number; ci: readonly [number, number] };
  /** Winner confirm CI, shaded so the reader judges separation themselves. */
  winnerCi?: readonly [number, number];
  width?: number;
  height?: number;
}

const PAD = 4;

export function ConvergencePlot({
  tpe,
  random,
  baseline,
  winnerCi,
  width = 320,
  height = 160,
}: ConvergencePlotProps) {
  if (tpe.length === 0 && random.length === 0) {
    return (
      <p role="note" className="font-mono text-xs opacity-50">
        no trials yet
      </p>
    );
  }

  const all = [...tpe, ...random];
  const maxTrial = Math.max(...all.map((p) => p.trial), 1);
  const ys = [...all.map((p) => p.bestSoFar), baseline.ci[0], baseline.ci[1], ...(winnerCi ?? [])];
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys) || 1;
  const ySpan = yMax - yMin || 1;

  const sx = (trial: number) => PAD + ((trial - 1) / Math.max(1, maxTrial - 1)) * (width - 2 * PAD);
  const sy = (value: number) => height - PAD - ((value - yMin) / ySpan) * (height - 2 * PAD);

  const points = (series: readonly ConvergencePoint[]) =>
    series.map((p) => `${sx(p.trial).toFixed(1)},${sy(p.bestSoFar).toFixed(1)}`).join(" ");

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      role="img"
      aria-label="Optimization convergence (best-so-far mean xG per trial)"
    >
      {winnerCi ? (
        <rect
          data-chart="winner-band"
          x={PAD}
          y={sy(winnerCi[1])}
          width={width - 2 * PAD}
          height={Math.max(0, sy(winnerCi[0]) - sy(winnerCi[1]))}
          fill="var(--color-signal)"
          fillOpacity={0.12}
        />
      ) : null}

      <line
        data-chart="baseline"
        x1={PAD}
        x2={width - PAD}
        y1={sy(baseline.mean)}
        y2={sy(baseline.mean)}
        stroke="var(--color-warn)"
        strokeWidth={1}
        strokeDasharray="4 3"
      />

      {random.length > 0 ? (
        <polyline
          data-chart="convergence-line"
          data-series="random"
          points={points(random)}
          fill="none"
          stroke="var(--color-line)"
          strokeOpacity={0.6}
          strokeWidth={1.5}
        />
      ) : null}

      {tpe.length > 0 ? (
        <polyline
          data-chart="convergence-line"
          data-series="tpe"
          points={points(tpe)}
          fill="none"
          stroke="var(--color-signal)"
          strokeWidth={2}
        />
      ) : null}
    </svg>
  );
}

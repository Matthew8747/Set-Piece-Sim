"use client";

// The search-space "wow" view (doc 07 §3): one polyline per trial across the
// genome axes, ordered by SHAP importance so the eye reads the strongest knobs
// first. Mixed types: continuous axes normalize to their [min,max] domain;
// categorical axes ladder by their category order. Stroke opacity encodes the
// trial's mean xG so high-value plays stand out of the cloud.

export interface PcAxis {
  name: string;
  kind: "continuous" | "categorical";
  /** [min, max] for continuous axes. */
  domain?: readonly number[];
  /** Category order for categorical axes. */
  categories?: readonly string[];
  importance: number;
}

export interface PcTrial {
  params: Record<string, number | string>;
  value: number;
}

export interface ParallelCoordinatesProps {
  trials: readonly PcTrial[];
  axes: readonly PcAxis[];
  width?: number;
  height?: number;
}

/** Map a raw param value onto [0,1] along its axis. Continuous → linear in the
 *  domain (clamped); categorical → index / (n-1), with a single-category axis
 *  pinned to the middle. Exported for unit testing the normalization math. */
export function normAxis(axis: PcAxis, value: number | string | undefined): number {
  if (value === undefined) return 0.5; // a missing param sits neutrally mid-axis
  if (axis.kind === "continuous") {
    const [min, max] = [axis.domain?.[0] ?? 0, axis.domain?.[1] ?? 1];
    const span = max - min || 1;
    const t = (Number(value) - min) / span;
    return Math.max(0, Math.min(1, t));
  }
  const cats = axis.categories ?? [];
  if (cats.length <= 1) return 0.5;
  const idx = Math.max(0, cats.indexOf(String(value)));
  return idx / (cats.length - 1);
}

const PAD = 8;

export function ParallelCoordinates({
  trials,
  axes,
  width = 480,
  height = 200,
}: ParallelCoordinatesProps) {
  if (trials.length === 0 || axes.length === 0) {
    return (
      <p role="note" className="font-mono text-xs opacity-50">
        no trials to plot
      </p>
    );
  }

  const innerH = height - 2 * PAD;
  const axisX = (i: number) =>
    axes.length === 1 ? width / 2 : PAD + (i / (axes.length - 1)) * (width - 2 * PAD);
  // value (0 bottom, 1 top) → screen y.
  const valueY = (t: number) => height - PAD - t * innerH;

  const values = trials.map((tr) => tr.value);
  const vMin = Math.min(...values);
  const vMax = Math.max(...values);
  const vSpan = vMax - vMin || 1;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      role="img"
      aria-label="Parallel coordinates of optimizer trials across genome axes"
    >
      {axes.map((axis, i) => (
        <line
          key={axis.name}
          data-chart="pc-axis"
          x1={axisX(i)}
          x2={axisX(i)}
          y1={PAD}
          y2={height - PAD}
          stroke="var(--color-line)"
          strokeOpacity={0.3}
          strokeWidth={1}
        />
      ))}

      {trials.map((trial, ti) => {
        const pts = axes
          .map(
            (axis, i) =>
              `${axisX(i).toFixed(1)},${valueY(normAxis(axis, trial.params[axis.name])).toFixed(1)}`,
          )
          .join(" ");
        // Higher mean xG → more opaque, so the good plays read out of the cloud.
        const opacity = 0.15 + 0.75 * ((trial.value - vMin) / vSpan);
        return (
          <polyline
            key={ti}
            data-chart="pc-trial"
            points={pts}
            fill="none"
            stroke="var(--color-signal)"
            strokeOpacity={opacity}
            strokeWidth={1}
          />
        );
      })}
    </svg>
  );
}

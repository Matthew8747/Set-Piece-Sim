"use client";

// Top-k confirmed routines vs the library baseline. A routine only earns the
// "beats baseline" marker when its CI lower bound clears the baseline CI upper
// bound (non-overlapping 95% CIs - the honest bar from doc 09 §4). Anti-exploit
// flags (bound-pinning / face-validity) ride along so a flagged "winner" is
// never read uncritically.

export interface TopKRow {
  label?: string;
  meanXg: number;
  ciLo: number;
  ciHi: number;
}

export interface TopKTableProps {
  rows: readonly TopKRow[];
  baseline: { mean: number; ci: readonly [number, number] };
  flags?: { boundary: readonly string[]; faceValidity: readonly string[] };
}

const pct = (v: number) => `${(v * 100).toFixed(2)}%`;

export function TopKTable({ rows, baseline, flags }: TopKTableProps) {
  if (rows.length === 0) {
    return (
      <p role="note" className="font-mono text-xs opacity-50">
        no confirmed routines
      </p>
    );
  }
  const baselineHi = baseline.ci[1];

  return (
    <table className="w-full font-mono text-xs tabular-nums" data-chart="topk">
      <thead>
        <tr className="text-left opacity-60">
          <th>routine</th>
          <th>mean xG</th>
          <th>95% CI</th>
          <th>vs baseline</th>
        </tr>
      </thead>
      <tbody>
        <tr data-chart="topk-baseline" className="opacity-60">
          <td>library baseline</td>
          <td>{pct(baseline.mean)}</td>
          <td>
            [{pct(baseline.ci[0])}, {pct(baseline.ci[1])}]
          </td>
          <td>-</td>
        </tr>
        {rows.map((row, i) => {
          const beats = row.ciLo > baselineHi;
          return (
            <tr key={i} data-chart="topk-row" data-beats={beats ? "true" : "false"}>
              <td>{row.label ?? `#${i + 1}`}</td>
              <td>{pct(row.meanXg)}</td>
              <td>
                [{pct(row.ciLo)}, {pct(row.ciHi)}]
              </td>
              <td>{beats ? "beats ✓" : "no sig. diff"}</td>
            </tr>
          );
        })}
      </tbody>
      {flags && (flags.boundary.length > 0 || flags.faceValidity.length > 0) ? (
        <tfoot>
          <tr>
            <td colSpan={4} className="pt-2 text-[var(--color-warn)]" data-chart="topk-flags">
              {[...flags.boundary, ...flags.faceValidity].join(" · ")}
            </td>
          </tr>
        </tfoot>
      ) : null}
    </table>
  );
}

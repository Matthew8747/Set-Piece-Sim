/**
 * @restart/pitch-kit — the canonical pitch surface, replay transport, and
 * hand-rolled SVG chart primitives shared across the Restart Lab frontend
 * (design doc 07). Charts are plain SVG, not visx (ADR-007 d7: visx peers cap
 * at React 18; the app is React 19).
 */

export { Pitch, type PitchProps } from "./Pitch";
export { ReplayPlayer, type ReplayPlayerProps, type ReplayEvent } from "./ReplayPlayer";
export { Histogram, type HistogramProps } from "./charts/Histogram";
export { Ecdf, type EcdfProps } from "./charts/Ecdf";
export { KpiCard, type KpiCardProps } from "./charts/KpiCard";
export {
  ConvergencePlot,
  type ConvergencePlotProps,
  type ConvergencePoint,
} from "./charts/ConvergencePlot";
export {
  ParallelCoordinates,
  normAxis,
  type ParallelCoordinatesProps,
  type PcAxis,
  type PcTrial,
} from "./charts/ParallelCoordinates";
export { TopKTable, type TopKTableProps, type TopKRow } from "./charts/TopKTable";
export {
  PX_PER_M,
  GOAL_LINE_X,
  VIEW_X_MIN,
  HALF_WIDTH,
  PITCH_W,
  PITCH_H,
  screenX,
  screenY,
  snap,
  type Point,
  type Frame,
} from "./geometry";

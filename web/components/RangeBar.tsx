"use client";
const MIN = 1.5, MAX = 7.5; // percent; one fixed scale so bars on different offers can be compared at a glance
const pos = (v: number) => Math.max(0, Math.min(100, ((v - MIN) / (MAX - MIN)) * 100));

/** Fair-rate band (green) with a marker for an offer's rate. Marker colour follows the verdict: green in range, amber slightly above, red above. */
export function RangeBar({ range, value, tone }: { range: [number, number]; value?: number; tone?: "ok" | "above" | "high" | "below" }) {
  return (
    <div className={`rb ${tone ?? ""}`} role="img" aria-label={`Fair range ${range[0]} to ${range[1]} percent${value !== undefined ? `, this offer ${value} percent` : ""}`} style={{ height: 44 }}>
      <div className="track" />
      <div className="band" style={{ left: `${pos(range[0])}%`, width: `${pos(range[1]) - pos(range[0])}%` }} />
      {value !== undefined && <div className="mark" style={{ left: `${pos(value)}%` }} />}
      <span className="lab" style={{ left: `${pos(range[0])}%` }}>{range[0].toFixed(1)}%</span>
      <span className="lab" style={{ left: `${pos(range[1])}%` }}>{range[1].toFixed(1)}%</span>
    </div>
  );
}

// Illustrative helpers for the screens. Real offer costs come from the Marketplace; these only give a feel for the numbers.
const RANGES: Record<string, [number, number]> = { A: [2.2, 3.0], B: [2.6, 3.4], C: [3.2, 4.4], D: [4.2, 6.0] };

/** Illustrative fair-rate band derived from the rating. Replaced by real benchmark data once enough offers exist. */
export function fairRange(category?: string): [number, number] | null {
  return category && RANGES[category] ? RANGES[category] : null;
}

export function fairTag(rate: number, range: [number, number] | null): { label: string; cls: "ok" | "above" | "high" | "below" } | null {
  if (!range) return null;
  if (rate < range[0] - 0.05) return { label: "Below fair range", cls: "below" };
  if (rate <= range[1] + 0.05) return { label: "In fair range", cls: "ok" };
  if (rate <= range[1] + 0.8) return { label: "Slightly above", cls: "above" };
  return { label: "Above fair range", cls: "high" };
}

/** Monthly instalment for an annuity loan (display only). */
export function monthlyAnnuity(amount: number, ratePct: number, months: number): number {
  const r = ratePct / 100 / 12;
  if (!months) return 0;
  return r === 0 ? amount / months : (amount * r) / (1 - Math.pow(1 + r, -months));
}

export const fmtRange = (r: [number, number] | null) => (r ? `${r[0].toFixed(1)}–${r[1].toFixed(1)}%` : "n/a");

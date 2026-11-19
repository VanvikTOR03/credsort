// Display formatting only. Money arrives as decimal strings and is never computed in the browser, except for non-binding previews.
const NBSP = " ";
export function chf(v: string | number | null | undefined, opts: { decimals?: number; compact?: boolean } = {}): string {
  if (v === null || v === undefined || v === "") return "n/a";
  const n = Number(v);
  if (!isFinite(n)) return "n/a";
  if (opts.compact && Math.abs(n) >= 1000) {
    if (Math.abs(n) >= 1_000_000) return `CHF${NBSP}${trim(n / 1_000_000)}M`;
    return `CHF${NBSP}${Math.round(n / 1000)}k`;
  }
  const d = opts.decimals ?? 0;
  return `CHF${NBSP}${n.toLocaleString("de-CH", { minimumFractionDigits: d, maximumFractionDigits: d })}`;
}
const trim = (n: number) => String(Math.round(n * 10) / 10);
export const pct = (v: string | number | null | undefined, d = 1) => (v === null || v === undefined || v === "" ? "n/a" : `${(Number(v) * (Math.abs(Number(v)) <= 5 ? 100 : 1)).toFixed(d)}%`);
export const ratePct = (v: string | number) => `${Number(v).toFixed(2)}%`;
export const ratio = (v: string | number | null | undefined, d = 2) => (v === null || v === undefined || v === "" ? "n/a" : Number(v).toFixed(d));
export function date(v?: string | null): string {
  if (!v) return "";
  return new Date(v).toLocaleDateString("en-CH", { day: "numeric", month: "short", year: "numeric" });
}
export function ago(v?: string | null): string {
  if (!v) return "";
  const s = (Date.now() - new Date(v).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)} d ago`;
  return date(v);
}
export function daysLeft(v?: string | null): number {
  if (!v) return 0;
  return Math.max(0, Math.ceil((new Date(v).getTime() - Date.now()) / 86400000));
}
/** Postel's law: accept "300000", "300'000", "300 000", "300k", "1.2m". Returns a decimal string or null. */
export function parseAmount(raw: string): string | null {
  const t = raw.toLowerCase().replace(/chf|[\s'’,]/g, "");
  const m = /^(\d+(?:\.\d+)?)([km])?$/.exec(t);
  if (!m) return null;
  const mult = m[2] === "k" ? 1000 : m[2] === "m" ? 1_000_000 : 1;
  const n = Math.round(parseFloat(m[1]) * mult * 100) / 100;
  return n > 0 ? String(n) : null;
}
export const groupDigits = (v: string) => (v === "" ? "" : Number(v).toLocaleString("de-CH", { maximumFractionDigits: 2 }));
export const cap = (s: string) => s.charAt(0) + s.slice(1).toLowerCase().replace(/_/g, " ");

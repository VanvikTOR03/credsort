"use client";
import { useCallback, useEffect, useRef, useState } from "react";

export type Problem = { status: number; code?: string; detail: string; fields?: Record<string, string> };
let csrf = "";
export const setCsrf = (v: string) => { csrf = v; };

function toProblem(status: number, body: any): Problem {
  const d = body?.detail;
  if (Array.isArray(d)) return { status, code: "validation", detail: d.map((x: any) => x.msg).join("; ") };
  return { status, code: body?.code, detail: typeof d === "string" ? d : "Something went wrong. Please try again." };
}

export async function api<T = any>(service: string, path: string, init: { method?: string; body?: unknown; idem?: string } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (init.body !== undefined) headers["content-type"] = "application/json";
  if (init.method && init.method !== "GET") headers["x-csrf"] = csrf;
  if (init.idem) headers["idempotency-key"] = init.idem;
  const res = await fetch(`/api/${service}${path}`, { method: init.method ?? "GET", headers, body: init.body !== undefined ? JSON.stringify(init.body) : undefined, cache: "no-store" });
  const text = await res.text();
  const json = text ? JSON.parse(text) : null;
  if (res.status === 401 && typeof window !== "undefined" && !location.pathname.startsWith("/login")) location.href = "/login";
  if (!res.ok) throw toProblem(res.status, json);
  return json as T;
}
export const newKey = () => (typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : String(Math.random()).slice(2));

// Stale-while-revalidate cache: screens paint instantly from the last answer, then refresh (Doherty threshold).
const cache = new Map<string, unknown>();
const listeners = new Set<() => void>();
export function invalidate(prefix = "") { for (const k of [...cache.keys()]) if (k.startsWith(prefix)) cache.delete(k); listeners.forEach((l) => l()); }

export function useApi<T = any>(service: string, path: string | null, opts: { refresh?: number } = {}) {
  const key = path ? `${service}${path}` : null;
  const [data, setData] = useState<T | undefined>(key ? (cache.get(key) as T | undefined) : undefined);
  const [error, setError] = useState<Problem | null>(null);
  const [loading, setLoading] = useState(!!key && !cache.has(key));
  const alive = useRef(true);
  const load = useCallback(async () => {
    if (!key || !path) return;
    try { const d = await api<T>(service, path); cache.set(key, d); if (alive.current) { setData(d); setError(null); } }
    catch (e) { if (alive.current) setError(e as Problem); }
    finally { if (alive.current) setLoading(false); }
  }, [key, service, path]);
  useEffect(() => {
    alive.current = true;
    if (key) { setData(cache.get(key) as T | undefined); setLoading(!cache.has(key)); setError(null); load(); } else { setData(undefined); setLoading(false); }
    const l = () => load(); listeners.add(l);
    const t = opts.refresh ? setInterval(load, opts.refresh) : undefined;
    return () => { alive.current = false; listeners.delete(l); if (t) clearInterval(t); };
  }, [key, load, opts.refresh]);
  return { data, error, loading, reload: load };
}

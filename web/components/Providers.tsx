"use client";
import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { setCsrf } from "@/lib/client/api";
import { Icon } from "./Icon";

export type Org = { id: string; name: string; type: string; role: string; kyb_status: string; on_behalf_of?: string | null };
export type SessionInfo = { authenticated: boolean; csrf: string; user: { email: string; name: string }; org: Org; memberships: any[]; actingFor: { id: string; name: string } | null };
const Ctx = createContext<{ session: SessionInfo | null; reload: () => Promise<void> }>({ session: null, reload: async () => {} });
export const useSession = () => useContext(Ctx);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [checked, setChecked] = useState(false);
  const reload = useCallback(async () => {
    const r = await fetch("/api/session", { cache: "no-store" });
    if (r.ok) { const s = await r.json(); setCsrf(s.csrf); setSession(s); }
    else if (!location.pathname.startsWith("/login")) location.href = "/login";
    setChecked(true);
  }, []);
  useEffect(() => { reload(); }, [reload]);
  if (!checked || !session) return <div style={{ minHeight: "100dvh", display: "grid", placeItems: "center" }}><div className="spinner" style={{ color: "var(--accent)" }} /></div>;
  return <Ctx.Provider value={{ session, reload }}>{children}</Ctx.Provider>;
}

type Toast = { id: number; text: string; kind: "ok" | "error" };
const ToastCtx = createContext<(text: string, kind?: "ok" | "error") => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, kind: "ok" | "error" = "ok") => {
    const id = Date.now() + Math.random();
    setItems((t) => [...t, { id, text, kind }]);
    setTimeout(() => setItems((t) => t.filter((x) => x.id !== id)), kind === "error" ? 5200 : 2800);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (
          <div className="toast" key={t.id}>
            <span className={`tile xs c-${t.kind === "ok" ? "green" : "red"}`}><Icon name={t.kind === "ok" ? "check" : "warning"} /></span>{t.text}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

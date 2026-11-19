"use client";
import React, { useEffect, useState } from "react";
import { Icon, Tile } from "@/components/Icon";
import { Seg } from "@/components/ui";

type Acct = { group: string; email: string; name: string; org: string; note: string; icon: string; color: string };
const GROUPS = [{ value: "SME", label: "Company" }, { value: "Lender", label: "Lender" }, { value: "Accountant", label: "Accountant" }, { value: "Operator", label: "Operator" }];

export default function Login() {
  const [accts, setAccts] = useState<Acct[] | null>(null);
  const [group, setGroup] = useState("SME");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { fetch("/api/auth/demo").then((r) => (r.ok ? r.json() : [])).then(setAccts).catch(() => setAccts([])); }, []);

  async function go(a: Acct) {
    setBusy(a.email); setErr("");
    const r = await fetch("/api/auth/login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: a.email, name: a.name }) });
    if (r.ok) { location.href = "/"; return; }
    const j = await r.json().catch(() => ({}));
    setErr(j.detail || "Could not sign in. Is the backend running?"); setBusy(null);
  }

  return (
    <div className="login-bg">
      <div className="page" style={{ maxWidth: 520, paddingTop: "max(8vh, 40px)" }}>
        <div className="stack-l">
          <div className="stack center enter" style={{ alignItems: "center" }}>
            <Tile name="franc" color="accent" size="xl" />
            <div><h1 className="t-large">CredSort</h1><p className="muted" style={{ marginTop: 6 }}>One profile. Many lenders. Your best rate.</p></div>
          </div>
          {accts === null && <div className="center muted"><span className="spinner" /></div>}
          {accts && accts.length === 0 && (
            <div className="card enter"><h2 className="t-head">Sign in with your organization</h2><p className="muted" style={{ marginTop: 6 }}>Single sign-on through Keycloak is the production sign-in and is not connected in this build.</p></div>
          )}
          {accts && accts.length > 0 && (
            <div className="stack enter" style={{ "--i": 1 } as React.CSSProperties}>
              <div className="center"><Seg label="Who are you?" options={GROUPS} value={group} onChange={setGroup} /></div>
              <div className="list" key={group}>
                {accts.filter((a) => a.group === group).map((a, i) => (
                  <button key={a.email} className="row enter" style={{ "--i": i } as React.CSSProperties} onClick={() => go(a)} disabled={!!busy}>
                    <Tile name={a.icon} color={a.color} />
                    <div className="grow"><div className="title">{a.org}</div><div className="sub">{a.name} · {a.note}</div></div>
                    {busy === a.email ? <span className="spinner" style={{ color: "var(--accent)" }} /> : <Icon name="chevron" className="chev" />}
                  </button>
                ))}
              </div>
              {err && <div className="banner" role="alert"><Tile name="warning" color="orange" size="sm" /><div>{err}</div></div>}
              <p className="t-foot center">Demo mode: tap a profile to sign in. All data is synthetic. No password is used.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

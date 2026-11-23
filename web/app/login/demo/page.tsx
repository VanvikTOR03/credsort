"use client";
import Link from "next/link";
import React, { useEffect, useState } from "react";
import { Icon, Logo, Tile } from "@/components/Icon";
import { Seg } from "@/components/ui";

type Acct = { group: string; email: string; name: string; org: string; icon: string };
type Tab = "company" | "lender" | "team";

/** Pre-made, synthetic accounts for demonstrations. One click signs in; these accounts have no password. */
export default function Demo() {
  const [accts, setAccts] = useState<Acct[] | null>(null);
  const [tab, setTab] = useState<Tab>("company");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { fetch("/api/auth/demo").then((r) => (r.ok ? r.json() : [])).then(setAccts).catch(() => setAccts([])); }, []);

  async function go(a: Acct) {
    setBusy(a.email); setErr("");
    const r = await fetch("/api/auth/demo-login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: a.email, name: a.name }) });
    if (r.ok) { location.href = "/"; return; }
    const j = await r.json().catch(() => ({}));
    setErr(j.detail || "Could not sign in."); setBusy(null);
  }
  const list = (accts ?? []).filter((a) => (tab === "company" ? a.group === "SME" : tab === "lender" ? a.group === "Lender" : ["Accountant", "Operator"].includes(a.group)));

  return (
    <main className="auth">
      <div className="auth-box">
        <div className="auth-card">
          <div className="auth-top">
            <Logo size="lg" />
            <h1 className="t-title">Demo</h1>
            <Seg full label="Demo accounts" options={[{ value: "company", label: "Company" }, { value: "lender", label: "Lender" }, { value: "team", label: "Team" }]} value={tab} onChange={setTab} />
          </div>
          {accts === null && <div className="center"><span className="spinner" /></div>}
          {accts && accts.length === 0 && <p className="center muted">No demo accounts here.</p>}
          {accts && accts.length > 0 && (
            <div className="list" key={tab}>
              {list.map((a, i) => (
                <button key={a.email} className="row enter" style={{ "--i": i } as React.CSSProperties} onClick={() => go(a)} disabled={!!busy}>
                  <Tile name={a.icon} size="sm" />
                  <div className="grow"><div className="title">{a.org}</div><div className="sub">{a.name}</div></div>
                  {busy === a.email ? <span className="spinner" /> : <Icon name="chevron" className="chev" />}
                </button>
              ))}
            </div>
          )}
          {err && <p className="field-error center" role="alert" style={{ padding: 0 }}>{err}</p>}
        </div>
        <div className="auth-links"><Link href="/login" className="btn plain">Back to sign in</Link></div>
      </div>
    </main>
  );
}

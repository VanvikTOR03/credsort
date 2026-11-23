"use client";
import Link from "next/link";
import React, { useEffect, useState } from "react";
import { Icon, Logo, Tile } from "@/components/Icon";
import { Seg } from "@/components/ui";

type Acct = { group: string; email: string; name: string; org: string; icon: string };
type Who = "company" | "lender";

export default function Login() {
  const [accts, setAccts] = useState<Acct[] | null>(null);
  const [who, setWho] = useState<Who>("company");
  const [staff, setStaff] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const [invite, setInvite] = useState(false), [code, setCode] = useState("");
  useEffect(() => { fetch("/api/auth/demo").then((r) => (r.ok ? r.json() : [])).then(setAccts).catch(() => setAccts([])); }, []);

  async function go(a: Acct) {
    setBusy(a.email); setErr("");
    const r = await fetch("/api/auth/login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: a.email, name: a.name }) });
    if (r.ok) { location.href = "/"; return; }
    const j = await r.json().catch(() => ({}));
    setErr(j.detail || "Could not sign in."); setBusy(null);
  }
  const list = (accts ?? []).filter((a) => (staff ? ["Accountant", "Operator"].includes(a.group) : who === "company" ? a.group === "SME" : a.group === "Lender"));

  return (
    <main className="auth">
      <div className="auth-box">
        <div className="auth-top">
          <Logo size="lg" />
          <Seg label="Sign in as" options={[{ value: "company", label: "Company" }, { value: "lender", label: "Lender" }]} value={who} onChange={(v) => { setWho(v); setStaff(false); }} />
        </div>

        {accts === null && <div className="center"><span className="spinner" /></div>}
        {accts && accts.length === 0 && <p className="center muted">Single sign-on is not connected.</p>}
        {accts && accts.length > 0 && (
          <div className="list" key={`${who}${staff}`}>
            {list.map((a, i) => (
              <button key={a.email} className="row enter" style={{ "--i": i } as React.CSSProperties} onClick={() => go(a)} disabled={!!busy}>
                <Tile name={a.icon} size="sm" />
                <div className="grow"><div className="title">{a.org}</div><div className="sub">{a.name}</div></div>
                {busy === a.email ? <span className="spinner" /> : <Icon name="chevron" className="chev" />}
              </button>
            ))}
          </div>
        )}
        {err && <p className="field-error center" role="alert">{err}</p>}

        <div className="auth-foot">
          {who === "company" && !staff && (
            <>
              <Link href="/signup" className="btn secondary block">Create account</Link>
              {!invite ? (
                <button className="btn plain" onClick={() => setInvite(true)}>Invitation code</button>
              ) : (
                <form className="hstack enter" style={{ width: "100%" }} onSubmit={(e) => { e.preventDefault(); if (code.trim()) location.href = `/signup?code=${encodeURIComponent(code.trim().toUpperCase())}`; }}>
                  <input className="in" value={code} onChange={(e) => setCode(e.target.value)} placeholder="CS-XXXXXX" aria-label="Invitation code" autoFocus />
                  <button className="btn" type="submit" disabled={!code.trim()}>Continue</button>
                </form>
              )}
            </>
          )}
          <button className="btn plain t-foot" onClick={() => setStaff(!staff)}>{staff ? "Back" : "Accountant or team"}</button>
        </div>
      </div>
    </main>
  );
}

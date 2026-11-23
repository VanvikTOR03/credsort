"use client";
import Link from "next/link";
import React, { useEffect, useState } from "react";
import { Logo } from "@/components/Icon";
import { Seg } from "@/components/ui";

type Who = "company" | "lender";

export default function Login() {
  const [who, setWho] = useState<Who>("company");
  const [accountant, setAccountant] = useState(false);
  const [email, setEmail] = useState(""), [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const [invite, setInvite] = useState(false), [code, setCode] = useState("");
  const [demo, setDemo] = useState(false);
  // The Demo link only exists where demo accounts exist (never in production).
  useEffect(() => { fetch("/api/auth/demo").then((r) => (r.ok ? r.json() : [])).then((l) => setDemo(Array.isArray(l) && l.length > 0)).catch(() => setDemo(false)); }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr("");
    const r = await fetch("/api/auth/login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email, password }) });
    if (r.ok) { location.href = "/"; return; }
    const j = await r.json().catch(() => ({}));
    setErr(j.detail ?? "Could not sign in."); setBusy(false);
  }
  const type = accountant ? "accountant" : who;

  return (
    <main className="auth">
      <div className="auth-box">
        <form className="auth-card" onSubmit={submit} noValidate>
          <div className="auth-top">
            <Logo size="lg" />
            {accountant ? <h1 className="t-title">Accountant sign-in</h1> : (
              <>
                <span className="auth-field-label">Sign in as</span>
                <Seg full label="Sign in as" options={[{ value: "company", label: "Company" }, { value: "lender", label: "Lender" }]} value={who} onChange={setWho} />
              </>
            )}
          </div>
          <div className="stack" style={{ gap: 14 }}>
            <div><label className="lbl" htmlFor="em">Email</label><input id="em" className="in" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus /></div>
            <div><label className="lbl" htmlFor="pw">Password</label><input id="pw" className="in" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
            {err && <p className="field-error" role="alert" style={{ padding: 0 }}>{err}</p>}
            <button className="btn block" type="submit" disabled={busy || !email || !password}>{busy && <span className="spinner" />}Sign in</button>
          </div>
        </form>

        <div className="auth-card slim">
          <Link href={`/signup?type=${type}`} className="btn secondary block">{accountant ? "Create accountant account" : "Create account"}</Link>
        </div>

        <div className="auth-links">
          {who === "company" && !accountant && <button type="button" className="btn plain" onClick={() => setInvite(!invite)}>Invitation code</button>}
          {who === "company" && !accountant && <button type="button" className="btn plain" onClick={() => setAccountant(true)}>Accountant or team</button>}
          {accountant && <button type="button" className="btn plain" onClick={() => setAccountant(false)}>Back</button>}
          {demo && <Link href="/login/demo" className="btn plain">Demo</Link>}
        </div>

        {invite && who === "company" && !accountant && (
          <div className="auth-invite enter">
            <input className="in" value={code} onChange={(e) => setCode(e.target.value)} placeholder="CS-XXXXXX" aria-label="Invitation code" autoFocus
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (code.trim()) location.href = `/signup?type=company&code=${encodeURIComponent(code.trim().toUpperCase())}`; } }} />
            <button type="button" className="btn" disabled={!code.trim()} onClick={() => { location.href = `/signup?type=company&code=${encodeURIComponent(code.trim().toUpperCase())}`; }}>Continue</button>
          </div>
        )}
      </div>
    </main>
  );
}

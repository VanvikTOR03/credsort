"use client";
import Link from "next/link";
import React, { useEffect, useState } from "react";
import { Icon, Tile } from "@/components/Icon";
import { Seg } from "@/components/ui";

type Acct = { group: string; email: string; name: string; org: string; note: string; icon: string; color: string };
type Who = "company" | "lender";
const COPY: Record<Who, { h: string; p: string; points: string[] }> = {
  company: { h: "Find the best loan for your business in 3 minutes.", p: "One profile, offers from Swiss banks and lenders, and an estimate of what a fair rate looks like for you.",
    points: ["Free to sign up, no credit check", "Your estimated rating and fair rate range", "Competing offers on one standard profile"] },
  lender: { h: "Meet SMEs that fit your book.", p: "Standardised, verified financial profiles. You set the criteria and only see companies that match.",
    points: ["Verified figures, one standard format", "Filter by your own criteria", "Offer in minutes, confirm payout when funded"] },
};

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
    setErr(j.detail || "Could not sign in. Is the backend running?"); setBusy(null);
  }
  const list = (accts ?? []).filter((a) => (staff ? ["Accountant", "Operator"].includes(a.group) : who === "company" ? a.group === "SME" : a.group === "Lender"));
  const c = COPY[who];

  return (
    <div className="split">
      <aside className="split-left">
        <div className="hstack"><Tile name="franc" color="blue" size="sm" /><b style={{ fontSize: 21, letterSpacing: "-.02em" }}>CredSort</b></div>
        <h1>{c.h}</h1>
        <p>{c.p}</p>
        <ul>{c.points.map((t) => <li key={t}><Icon name="check" />{t}</li>)}</ul>
        <div className="fine">Neutral marketplace. CredSort never lends and never makes the credit decision.</div>
      </aside>
      <main className="split-right">
        <div className="inner stack-l">
          <div className="stack">
            <h2 className="t-title" style={{ fontSize: 28 }}>Sign in</h2>
            <Seg label="Sign in as" options={[{ value: "company", label: "Company" }, { value: "lender", label: "Lender" }]} value={who} onChange={(v) => { setWho(v); setStaff(false); }} />
          </div>

          {accts === null && <span className="spinner" style={{ color: "var(--navy)" }} />}
          {accts && accts.length === 0 && (
            <div className="card stack-s"><b>Sign in with your organization</b><p className="muted">Single sign-on is not connected in this build.</p></div>
          )}
          {accts && accts.length > 0 && (
            <div className="stack">
              <p className="t-foot">{staff ? "CredSort team and accountants" : "Demo profiles. All data is synthetic and no password is used."}</p>
              <div className="list" key={`${who}${staff}`}>
                {list.map((a, i) => (
                  <button key={a.email} className="row enter" style={{ "--i": i } as React.CSSProperties} onClick={() => go(a)} disabled={!!busy}>
                    <Tile name={a.icon} color={a.color} />
                    <div className="grow"><div className="title">{a.org}</div><div className="sub">{a.name} · {a.note}</div></div>
                    {busy === a.email ? <span className="spinner" /> : <Icon name="chevron" className="chev" />}
                  </button>
                ))}
              </div>
              {err && <div className="banner" role="alert"><Tile name="warning" color="orange" size="sm" /><div>{err}</div></div>}
            </div>
          )}

          <div className="stack-s">
            {who === "company" && !staff && (
              <>
                <div className="hstack spread wrap"><span>New to CredSort?</span><Link href="/signup" className="btn secondary sm">Create a company account</Link></div>
                {!invite ? (
                  <button className="btn plain" style={{ alignSelf: "flex-start", padding: 0 }} onClick={() => setInvite(true)}>Invited by your fiduciary? Use your invitation code</button>
                ) : (
                  <form className="hstack enter" onSubmit={(e) => { e.preventDefault(); if (code.trim()) location.href = `/signup?code=${encodeURIComponent(code.trim().toUpperCase())}`; }}>
                    <input className="in" value={code} onChange={(e) => setCode(e.target.value)} placeholder="CS-XXXXXX" aria-label="Invitation code" autoFocus />
                    <button className="btn" type="submit" disabled={!code.trim()}>Continue</button>
                  </form>
                )}
              </>
            )}
            <button className="btn plain" style={{ alignSelf: "flex-start", padding: 0 }} onClick={() => setStaff(!staff)}>{staff ? "Back to company and lender sign-in" : "Accountant or CredSort team? Sign in here"}</button>
          </div>
        </div>
      </main>
    </div>
  );
}

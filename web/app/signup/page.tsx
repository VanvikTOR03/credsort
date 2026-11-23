"use client";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Icon, Tile } from "@/components/Icon";

const INDUSTRIES = [["manufacturing", "Manufacturing"], ["construction", "Construction and joinery"], ["hospitality", "Hospitality"], ["retail", "Retail"], ["software", "Software and IT"], ["healthcare", "Healthcare"], ["logistics", "Logistics"], ["services", "Other services"]];
const CANTONS = "AG AI AR BE BL BS FR GE GL GR JU LU NE NW OW SG SH SO SZ TG TI UR VD VS ZG ZH".split(" ");
const SIZES: [string, number][] = [["Fewer than 10", 5], ["10 to 49", 25], ["50 to 249", 100], ["250 or more", 300]];

function Form() {
  const q = useSearchParams();
  const [f, setF] = useState({ legal_name: "", uid: "", legal_form: "GmbH", industry: "manufacturing", canton: "ZH", employees: 25, name: "", email: "", referral_code: q.get("code") ?? "", terms: false });
  const [inviter, setInviter] = useState<string | null>(null), [codeErr, setCodeErr] = useState("");
  const [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const set = (k: string, v: any) => setF((x) => ({ ...x, [k]: v }));

  useEffect(() => {
    const code = f.referral_code.trim();
    setInviter(null); setCodeErr("");
    if (code.length < 4) return;
    let live = true;  // a slow answer for an old code must not overwrite the state of a newer one
    const t = setTimeout(async () => {
      const r = await fetch(`/api/auth/invite?code=${encodeURIComponent(code)}`);
      const j = await r.json().catch(() => ({}));
      if (!live) return;
      r.ok ? setInviter(j.name) : setCodeErr(j.detail ?? "Unknown code");
    }, 350);
    return () => { live = false; clearTimeout(t); };
  }, [f.referral_code]);

  const uidOk = /^CHE-\d{3}\.\d{3}\.\d{3}$/.test(f.uid);
  const ready = f.legal_name.trim().length > 1 && uidOk && f.name.trim().length > 1 && /\S+@\S+\.\S+/.test(f.email) && f.terms && !codeErr;

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr("");
    const r = await fetch("/api/auth/signup", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ ...f, referral_code: f.referral_code.trim().toUpperCase() || null }) });
    if (r.ok) { location.href = "/sme/loans/new?first=1"; return; }
    const j = await r.json().catch(() => ({}));
    setErr(j.detail ?? "Could not create the account."); setBusy(false);
  }

  return (
    <div className="split">
      <aside className="split-left">
        <div className="hstack"><Tile name="franc" color="blue" size="sm" /><b style={{ fontSize: 21, letterSpacing: "-.02em" }}>CredSort</b></div>
        <h1>Find the best loan for your business in 3 minutes.</h1>
        <p>One profile, offers from Swiss banks and lenders, and an estimate of what a fair rate looks like for you.</p>
        <ul>
          <li><Icon name="check" />Free to sign up, no credit check</li>
          <li><Icon name="check" />Your estimated rating and fair rate range</li>
          <li><Icon name="check" />Competing offers on one standard profile</li>
          <li><Icon name="check" />One-off CHF 190 only when you want to see who made the offers</li>
        </ul>
        <div className="fine">Neutral marketplace. CredSort never lends and never makes the credit decision.</div>
      </aside>
      <main className="split-right">
        <form className="inner stack" onSubmit={submit} noValidate>
          <div className="hstack spread"><h2 className="t-title" style={{ fontSize: 28 }}>Create your company account</h2><span className="t-foot" style={{ whiteSpace: "nowrap" }}>Step 1 of 3</span></div>
          <div className="steps" aria-hidden><i className="on" /><i /><i /></div>
          <div><label className="lbl" htmlFor="cn">Company name</label><input id="cn" className="in" value={f.legal_name} onChange={(e) => set("legal_name", e.target.value)} placeholder="Muster Schreinerei GmbH" autoComplete="organization" /></div>
          <div className="cols-2">
            <div><label className="lbl" htmlFor="uid">UID number</label><input id="uid" className={`in ${f.uid && !uidOk ? "err" : ""}`} value={f.uid} onChange={(e) => set("uid", e.target.value.toUpperCase())} placeholder="CHE-123.456.789" inputMode="text" /></div>
            <div><label className="lbl" htmlFor="lf">Legal form</label><select id="lf" className="in" value={f.legal_form} onChange={(e) => set("legal_form", e.target.value)}><option>GmbH</option><option>AG</option><option value="Other">Other</option></select></div>
            <div><label className="lbl" htmlFor="ind">Industry</label><select id="ind" className="in" value={f.industry} onChange={(e) => set("industry", e.target.value)}>{INDUSTRIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
            <div><label className="lbl" htmlFor="ct">Canton</label><select id="ct" className="in" value={f.canton} onChange={(e) => set("canton", e.target.value)}>{CANTONS.map((c) => <option key={c}>{c}</option>)}</select></div>
            <div><label className="lbl" htmlFor="sz">Company size</label><select id="sz" className="in" value={f.employees} onChange={(e) => set("employees", Number(e.target.value))}>{SIZES.map(([l, n]) => <option key={n} value={n}>{l}</option>)}</select></div>
            <div><label className="lbl" htmlFor="nm">Your name</label><input id="nm" className="in" value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="First and last name" autoComplete="name" /></div>
          </div>
          <div><label className="lbl" htmlFor="em">Business email</label><input id="em" className="in" type="email" value={f.email} onChange={(e) => set("email", e.target.value)} placeholder="name@company.ch" autoComplete="email" /></div>
          <div>
            <label className="lbl" htmlFor="inv">Invitation code from your fiduciary <span className="muted" style={{ fontWeight: 400 }}>(optional)</span></label>
            <input id="inv" className={`in ${codeErr ? "err" : ""}`} value={f.referral_code} onChange={(e) => set("referral_code", e.target.value.toUpperCase())} placeholder="CS-XXXXXX" />
            {inviter && <p className="t-foot" style={{ marginTop: 6, color: "var(--green)" }}>Invited by {inviter}</p>}
            {codeErr && <p className="field-error">{codeErr}</p>}
          </div>
          <label className="check"><input type="checkbox" checked={f.terms} onChange={(e) => set("terms", e.target.checked)} /><span>I agree to the terms and the privacy policy (data hosted in Switzerland).</span></label>
          {err && <div className="banner" role="alert">{err}</div>}
          <div className="hstack wrap">
            <button className="btn" type="submit" disabled={!ready || busy}>{busy ? <span className="spinner" /> : null}Create account</button>
            <span className="muted">or</span>
            <button className="btn secondary" type="button" disabled title="Coming soon">Sign up with Swiss e-ID <span className="pill" style={{ marginLeft: 6 }}>soon</span></button>
          </div>
          <p className="t-foot">Already have an account? <Link href="/login">Sign in</Link></p>
        </form>
      </main>
    </div>
  );
}
export default function Signup() { return <Suspense><Form /></Suspense>; }

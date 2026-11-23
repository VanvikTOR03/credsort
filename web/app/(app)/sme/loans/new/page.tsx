"use client";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, invalidate, newKey, useApi } from "@/lib/client/api";
import { Button, ErrorNote, Meter, PageHeader, Sheet } from "@/components/ui";
import { Icon, Tile } from "@/components/Icon";
import { useToast } from "@/components/Providers";
import { chf, date } from "@/lib/format";
import { monthlyAnnuity } from "@/lib/loan";

const PURPOSES = ["Machinery & equipment", "Working capital", "Vehicles", "Expansion or new site", "Refinance an existing loan", "Property or renovation", "Stock & inventory", "Succession or acquisition"];
const COLLATERAL = ["None", "The financed asset itself", "Property", "Receivables or stock", "Personal guarantee"];

function Page() {
  const router = useRouter(), toast = useToast(), q = useSearchParams();
  const draftId = q.get("draft"), first = q.get("first") === "1";
  const assess = useApi<any[]>("intelligence", "/v1/assessments", { refresh: 3000 });
  const conns = useApi<any[]>("accounting", "/v1/connections", { refresh: 3000 });
  const jobs = useApi<any[]>("accounting", "/v1/import-jobs", { refresh: 2000 });
  const [amount, setAmount] = useState(250000), [years, setYears] = useState(5), [purpose, setPurpose] = useState(PURPOSES[0]), [collateral, setCollateral] = useState(COLLATERAL[1]);
  const [agree, setAgree] = useState(false), [err, setErr] = useState<any>(null), [busy, setBusy] = useState(false);
  const [inviteSheet, setInviteSheet] = useState(false), [idem] = useState(newKey);

  useEffect(() => {
    if (!draftId) return;
    api("marketplace", `/v1/applications/${draftId}`).then((a) => { setAmount(Math.round(Number(a.amount))); setYears(Math.round(a.term_months / 12) || 1); if (a.purpose) setPurpose(a.purpose); if (a.collateral) setCollateral(a.collateral); }).catch(() => {});
  }, [draftId]);

  const hasData = !!assess.data?.length;
  const importing = jobs.data?.some((j) => ["QUEUED", "RUNNING"].includes(j.status)) || (!!conns.data?.length && !hasData);
  const progress = jobs.data?.find((j) => ["QUEUED", "RUNNING"].includes(j.status))?.progress ?? 10;
  const monthly = useMemo(() => monthlyAnnuity(amount, 3.0, years * 12), [amount, years]);
  const source = conns.data?.[0];

  async function demoData() {
    try {
      const c = await api("accounting", "/v1/connections", { method: "POST", body: { source_type: "SYNTHETIC", dataset: "muster" } });
      await api("accounting", "/v1/import-jobs", { method: "POST", body: { connection_id: c.id } });
      invalidate(); toast("Importing demo accounts");
    } catch (e: any) { toast(e.detail, "error"); }
  }
  async function bexio() {
    try { const r = await api("accounting", "/v1/connections/bexio/authorize"); location.href = r.url; }
    catch (e: any) { toast(e.code === "bexio_not_configured" ? "bexio is not set up on this server yet. Try the demo data." : e.detail, "error"); }
  }
  async function submit() {
    setErr(null); setBusy(true);
    try {
      const body = { amount: String(amount), term_months: years * 12, purpose, collateral: collateral === "None" ? null : collateral, assessment_id: assess.data![0].id };
      let id = draftId;
      if (id) await api("marketplace", `/v1/applications/${id}`, { method: "PATCH", body });
      else id = (await api("marketplace", "/v1/applications", { method: "POST", body })).id;
      await api("marketplace", `/v1/applications/${id}/publication`, { method: "POST", body: {}, idem: idem });
      invalidate(); router.push(`/sme/loans/${id}`);
    } catch (e: any) { setErr(e); setBusy(false); }
  }

  return (
    <div className="stack-l">
      {first ? (
        <div className="hstack spread wrap"><div className="hstack"><Tile name="franc" color="blue" size="sm" /><b style={{ fontSize: 19 }}>CredSort</b></div><div className="hstack" style={{ minWidth: 260 }}><span className="t-foot" style={{ whiteSpace: "nowrap" }}>Step 2 of 3 · about 2 minutes left</span><div style={{ flex: 1 }}><Meter value={2} max={3} label="Step 2 of 3" /></div></div></div>
      ) : null}
      <PageHeader title="What do you need?" back={first ? undefined : "/sme/loans"} subtitle="Set your loan and add your accounts. Lenders see one standard profile, not ten different forms." />

      <div className="need-grid">
        <div className="card stack-l">
          <div className="stack">
            <div className="hstack spread"><label className="lbl" htmlFor="amt" style={{ margin: 0 }}>Loan amount</label><b className="num t-title">{chf(amount)}</b></div>
            <input id="amt" className="range" type="range" min={25000} max={2000000} step={5000} value={amount} onChange={(e) => setAmount(Number(e.target.value))} />
            <div className="hstack spread t-foot"><span>CHF 25k</span><span>CHF 2M</span></div>
          </div>
          <div className="stack">
            <div className="hstack spread"><label className="lbl" htmlFor="term" style={{ margin: 0 }}>Term</label><b className="num t-title">{years} {years === 1 ? "year" : "years"}</b></div>
            <input id="term" className="range" type="range" min={1} max={10} step={1} value={years} onChange={(e) => setYears(Number(e.target.value))} />
            <div className="hstack spread t-foot"><span>1 year</span><span>10 years</span></div>
          </div>
          <div className="stack-s">
            <span className="lbl">What is the loan for?</span>
            <div className="hstack wrap">{PURPOSES.map((p) => <button key={p} className="chip" aria-pressed={purpose === p} onClick={() => setPurpose(p)}>{p}</button>)}</div>
          </div>
          <div><label className="lbl" htmlFor="col">Collateral available?</label><select id="col" className="in" value={collateral} onChange={(e) => setCollateral(e.target.value)}>{COLLATERAL.map((c) => <option key={c}>{c}</option>)}</select></div>

          <div className="stack-s">
            <span className="lbl">Add your accounts</span>
            {hasData && source ? (
              <div className="banner info"><Tile name="check" color="green" size="sm" /><div className="grow"><b>Accounts connected</b><div className="t-cap">{source.source_type === "BEXIO" ? "bexio" : "Demo accounts"} · figures to {date(source.last_period_end)}</div></div></div>
            ) : importing ? (
              <div className="banner info"><span className="spinner" /><div className="grow"><b>Checking your accounts</b><div className="t-cap">This takes a few seconds.</div><div style={{ marginTop: 8 }}><Meter value={progress} label="Import progress" /></div></div></div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 10 }}>
                <button className="btn secondary" onClick={bexio}><Icon name="refresh" />Connect bexio</button>
                <button className="btn secondary" onClick={demoData}><Icon name="doc" />Try demo accounts</button>
                <button className="btn secondary" disabled title="Coming soon"><Icon name="upload" />Upload annual accounts</button>
                <button className="btn secondary" onClick={() => setInviteSheet(true)}><Icon name="people" />Invite my fiduciary</button>
              </div>
            )}
          </div>
        </div>

        <div className="stack">
          <div className="navy-panel">
            <span className="t-over">Your request</span>
            <div className="stack-s">
              <div className="hstack spread"><span className="muted">Amount</span><b className="num">{chf(amount)}</b></div>
              <div className="hstack spread"><span className="muted">Term</span><b>{years} {years === 1 ? "year" : "years"}</b></div>
              <div className="hstack spread"><span className="muted">Purpose</span><b style={{ textAlign: "right" }}>{purpose}</b></div>
            </div>
            <div className="rule" />
            <div className="stack-s">
              <span className="muted">Estimated monthly instalment</span>
              <div className="num" style={{ fontSize: 34, fontWeight: 750, letterSpacing: "-.02em" }}>≈ {chf(monthly)}</div>
              <span className="t-foot">Illustrative, at 3.0% a year. Your real offers can differ.</span>
            </div>
          </div>
          <div className="card hstack" style={{ alignItems: "flex-start" }}><Tile name="spark" color="blue" size="sm" /><p>Tip from the assistant: with your accounts connected, lenders can make firm offers instead of rough estimates.</p></div>
          <label className="check"><input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} /><span>I agree to share my full company profile (figures, rating and company name) with lenders that match my request. I can stop sharing at any time.</span></label>
          <ErrorNote error={err} />
          <Button block onClick={submit} loading={busy} disabled={!hasData || !agree}>See my offers</Button>
          {!hasData && <p className="t-foot center">Add your accounts first so lenders can see real numbers.</p>}
        </div>
      </div>

      <Sheet open={inviteSheet} onClose={() => setInviteSheet(false)} title="Invite your fiduciary">
        <div className="stack">
          <p>Ask your fiduciary for their invitation code. Once you are signed in, enter it under <b>More, Accountant</b>. They can then prepare your request and add your accounts, but cannot choose an offer for you.</p>
          <Button block variant="secondary" onClick={() => setInviteSheet(false)}>Got it</Button>
        </div>
      </Sheet>
    </div>
  );
}
export default function NewLoan() { return <Suspense><Page /></Suspense>; }

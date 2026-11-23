"use client";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, invalidate, newKey, useApi } from "@/lib/client/api";
import { Button, Card, ErrorNote, Meter, PageHeader, Sheet } from "@/components/ui";
import { Icon, Tile } from "@/components/Icon";
import { useToast } from "@/components/Providers";
import { chf, date } from "@/lib/format";
import { monthlyAnnuity } from "@/lib/loan";

const PURPOSES = ["Machinery", "Working capital", "Vehicles", "Expansion", "Refinancing", "Property", "Inventory", "Succession"];
const COLLATERAL = ["None", "Financed asset", "Property", "Receivables or stock", "Personal guarantee"];

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
      invalidate();
    } catch (e: any) { toast(e.detail, "error"); }
  }
  async function bexio() {
    try { const r = await api("accounting", "/v1/connections/bexio/authorize"); location.href = r.url; }
    catch (e: any) { toast(e.code === "bexio_not_configured" ? "bexio is not set up on this server" : e.detail, "error"); }
  }
  async function submit() {
    setErr(null); setBusy(true);
    try {
      const body = { amount: String(amount), term_months: years * 12, purpose, collateral: collateral === "None" ? null : collateral, assessment_id: assess.data![0].id };
      let id = draftId;
      if (id) await api("marketplace", `/v1/applications/${id}`, { method: "PATCH", body });
      else id = (await api("marketplace", "/v1/applications", { method: "POST", body })).id;
      await api("marketplace", `/v1/applications/${id}/publication`, { method: "POST", body: {}, idem });
      invalidate(); router.push(`/sme/loans/${id}`);
    } catch (e: any) { setErr(e); setBusy(false); }
  }

  return (
    <div>
      <PageHeader title="Loan request" back={first ? undefined : "/sme/loans"} />
      <div className="need-grid">
        <div className="stack-l" style={{ gap: 20 }}>
          <Card className="stack-l" style={{ gap: 28 }}>
            <div className="stack">
              <div className="hstack spread"><label className="t-over" htmlFor="amt">Amount</label><b className="num t-title">{chf(amount)}</b></div>
              <input id="amt" className="range" type="range" min={25000} max={2000000} step={5000} value={amount} onChange={(e) => setAmount(Number(e.target.value))} />
              <div className="hstack spread t-cap"><span>CHF 25k</span><span>CHF 2M</span></div>
            </div>
            <div className="stack">
              <div className="hstack spread"><label className="t-over" htmlFor="term">Term</label><b className="num t-title">{years} {years === 1 ? "year" : "years"}</b></div>
              <input id="term" className="range" type="range" min={1} max={10} step={1} value={years} onChange={(e) => setYears(Number(e.target.value))} />
              <div className="hstack spread t-cap"><span>1 year</span><span>10 years</span></div>
            </div>
          </Card>
          <Card className="stack">
            <span className="t-over">Purpose</span>
            <div className="hstack wrap">{PURPOSES.map((p) => <button key={p} className="chip" aria-pressed={purpose === p} onClick={() => setPurpose(p)}>{p}</button>)}</div>
            <label className="t-over" htmlFor="col" style={{ marginTop: 8 }}>Collateral</label>
            <select id="col" className="in" value={collateral} onChange={(e) => setCollateral(e.target.value)}>{COLLATERAL.map((c) => <option key={c}>{c}</option>)}</select>
          </Card>
          <Card className="stack">
            <span className="t-over">Accounts</span>
            {hasData && source ? (
              <div className="hstack"><Tile name="check" size="sm" /><div style={{ flex: 1 }}>{source.source_type === "BEXIO" ? "bexio" : "Demo accounts"}<span className="muted"> · {date(source.last_period_end)}</span></div></div>
            ) : importing ? (
              <div className="hstack"><span className="spinner" /><div style={{ flex: 1 }}><Meter value={progress} label="Import progress" /></div></div>
            ) : (
              <div className="grid c2">
                <button className="btn secondary" onClick={bexio}><Icon name="refresh" />bexio</button>
                <button className="btn secondary" onClick={demoData}><Icon name="doc" />Demo accounts</button>
                <button className="btn secondary" disabled><Icon name="upload" />Upload</button>
                <button className="btn secondary" onClick={() => setInviteSheet(true)}><Icon name="people" />Fiduciary</button>
              </div>
            )}
          </Card>
        </div>

        <aside className="panel stack">
          <dl className="kv"><dt>Amount</dt><dd>{chf(amount)}</dd><dt>Term</dt><dd>{years} {years === 1 ? "year" : "years"}</dd><dt>Purpose</dt><dd>{purpose}</dd></dl>
          <hr className="sep" />
          <div className="kpi"><span className="l">Monthly</span><span className="v">≈ {chf(monthly)}</span><span className="c">3.0% a year, illustrative</span></div>
          <hr className="sep" />
          <label className="check"><input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} /><span>Share my full profile with matching lenders.</span></label>
          <ErrorNote error={err} />
          <Button block onClick={submit} loading={busy} disabled={!hasData || !agree}>Request offers</Button>
        </aside>
      </div>

      <Sheet open={inviteSheet} onClose={() => setInviteSheet(false)} title="Fiduciary">
        <div className="stack"><p>Enter your fiduciary's code under More, Accountant.</p><Button block variant="secondary" onClick={() => setInviteSheet(false)}>Close</Button></div>
      </Sheet>
    </div>
  );
}
export default function NewLoan() { return <Suspense><Page /></Suspense>; }

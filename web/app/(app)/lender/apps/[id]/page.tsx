"use client";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { api, invalidate, newKey, useApi } from "@/lib/client/api";
import { Button, Card, ErrorNote, Field, List, PageHeader, Pill, Row, Section, Sheet, Skeleton, Switch, Success } from "@/components/ui";
import { Tile } from "@/components/Icon";
import { useToast } from "@/components/Providers";
import { FIELD_PLAIN } from "@/lib/labels";
import { chf, pct, ratePct } from "@/lib/format";

function show(field: string, v: any) {
  if (["requested_amount", "revenue", "working_capital"].includes(field)) return chf(v);
  if (["revenue_growth", "ebitda_margin", "net_profit_margin", "equity_ratio"].includes(field)) return pct(v);
  if (["current_ratio", "debt_to_ebitda", "dscr"].includes(field)) return `${Number(v).toFixed(2)}×`;
  if (field === "term_months") return `${v} months`;
  return typeof v === "string" && !/\d/.test(v) ? v.charAt(0).toUpperCase() + v.slice(1).toLowerCase() : String(v);
}
const inDays = (n: number) => new Date(Date.now() + n * 86400000).toISOString().slice(0, 10);

export default function LenderApp() {
  const { id } = useParams<{ id: string }>(), router = useRouter(), toast = useToast();
  const a = useApi<any>("marketplace", `/v1/lender/applications/${id}`, { refresh: 15000 });
  const cat = useApi<{ fields: { field: string; label: string }[] }>("marketplace", "/v1/field-catalogue");
  const [offer, setOffer] = useState(false), [more, setMore] = useState(false), [err, setErr] = useState<any>(null), [sent, setSent] = useState(false);
  const [f, setF] = useState({ amount: "", rate: "3.5", term_months: "60", fees: "0", repayment: "LINEAR", collateral: "", valid_until: inDays(30) });
  const [ask, setAsk] = useState<Set<string>>(new Set());
  const d = a.data;
  const hidden = (cat.data?.fields ?? []).filter((x) => d && !(x.field in d.fields));

  async function submitOffer() {
    setErr(null);
    try {
      await api("marketplace", `/v1/lender/applications/${id}/offers`, { method: "POST", idem: newKey(), body: { amount: f.amount || d.fields.requested_amount, rate: f.rate, term_months: Number(f.term_months), fees: f.fees || "0", repayment: f.repayment, collateral: f.collateral || null, valid_until: f.valid_until } });
      invalidate(); setOffer(false); setSent(true);
    } catch (e: any) { setErr(e); }
  }
  async function request() {
    setErr(null);
    try { await api("marketplace", `/v1/lender/applications/${id}/access-requests`, { method: "POST", body: { fields: [...ask] } }); invalidate(); setMore(false); toast("Request sent. The company decides."); } catch (e: any) { setErr(e); }
  }
  if (a.loading) return <div className="stack-l"><PageHeader title="Company" back="/lender" /><Skeleton h={220} r={20} /></div>;
  if (!d) return <div className="stack-l"><PageHeader title="Company" back="/lender" /><ErrorNote error={a.error} retry={a.reload} /></div>;
  const fields = Object.entries(d.fields as Record<string, unknown>);
  return (
    <div className="stack-l">
      <PageHeader title={d.fields.requested_amount ? chf(d.fields.requested_amount) : "Company"} back="/lender" subtitle={`${d.fields.industry ?? "Industry not shared"} · figures as of ${d.as_of}`} />
      {sent && <Card><Success title="Offer sent" text="The company can now compare it with others. You will hear when they choose."><Button onClick={() => router.push("/lender/offers")}>View my offers</Button></Success></Card>}
      {!sent && (
        <div className="hstack">
          <div className="grow">{d.my_offer ? <Button block variant="secondary" href="/lender/offers">You already made an offer</Button> : <Button block onClick={() => { setF({ ...f, amount: String(Math.round(Number(d.fields.requested_amount ?? 0)) || "") }); setOffer(true); }}>Make an offer</Button>}</div>
        </div>
      )}
      <Section title="What the company shared" footer="You only see what the company chose to share. Matching uses these same details and nothing else.">
        <List>{fields.map(([k, v]) => <Row key={k} noicon title={d.labels[k] ?? k} value={<b style={{ color: "var(--label)" }}>{show(k, v)}</b>} />)}</List>
      </Section>
      {d.match && (
        <Section title="Why it matches">
          <List>{d.match.explanation.map((e: any, i: number) => <Row key={i} icon={e.met ? "check" : "x"} color={e.met ? "green" : "red"} title={e.criterion} value={<span className="num">{e.actual}</span>} />)}</List>
        </Section>
      )}
      {hidden.length > 0 && (
        <Card className="stack-s">
          <div className="hstack"><Tile name="eye" color="indigo" size="sm" /><b>Need more detail?</b></div>
          <p className="muted">{d.access_request?.status === "PENDING" ? "Your request is waiting for the company." : "Ask for extra figures. The company decides whether to share them."}</p>
          {d.access_request?.status !== "PENDING" && <Button variant="secondary" onClick={() => setMore(true)}>Ask for more</Button>}
        </Card>
      )}
      <Sheet open={offer} onClose={() => setOffer(false)} title="Your offer">
        <div className="stack">
          <List>
            <Field label="Amount (CHF)"><input inputMode="decimal" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} /></Field>
            <Field label="Interest rate (% a year)"><input inputMode="decimal" value={f.rate} onChange={(e) => setF({ ...f, rate: e.target.value })} /></Field>
            <Field label="Term (months)"><input inputMode="numeric" value={f.term_months} onChange={(e) => setF({ ...f, term_months: e.target.value })} /></Field>
            <Field label="Your fees (CHF)"><input inputMode="decimal" value={f.fees} onChange={(e) => setF({ ...f, fees: e.target.value })} /></Field>
            <Field label="Repayment"><select value={f.repayment} onChange={(e) => setF({ ...f, repayment: e.target.value })}><option value="LINEAR">Equal principal</option><option value="ANNUITY">Equal payments</option><option value="BULLET">At the end</option></select></Field>
            <Field label="Security"><input value={f.collateral} onChange={(e) => setF({ ...f, collateral: e.target.value })} placeholder="Optional" /></Field>
            <Field label="Valid until"><input type="date" value={f.valid_until} onChange={(e) => setF({ ...f, valid_until: e.target.value })} /></Field>
          </List>
          <p className="t-foot">An offer cannot be changed once sent. You can withdraw it while the company has not chosen it.</p>
          <ErrorNote error={err} />
          <Button block onClick={submitOffer}>Send offer</Button>
        </div>
      </Sheet>
      <Sheet open={more} onClose={() => setMore(false)} title="Ask for more detail">
        <div className="stack">
          <List>{hidden.map((x) => <Row key={x.field} noicon title={x.label} sub={FIELD_PLAIN[x.field]}><Switch label={x.label} checked={ask.has(x.field)} onChange={(v) => setAsk((s) => { const n = new Set(s); v ? n.add(x.field) : n.delete(x.field); return n; })} /></Row>)}</List>
          <ErrorNote error={err} /><Button block onClick={request} disabled={ask.size === 0}>Send request</Button>
        </div>
      </Sheet>
    </div>
  );
}

"use client";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, invalidate, newKey, useApi } from "@/lib/client/api";
import { Button, Card, ErrorNote, Field, List, PageHeader, Pill, Row, Section, Steps, Success, Switch, Skeleton } from "@/components/ui";
import { Icon, Tile } from "@/components/Icon";
import { FIELD_GROUPS, FIELD_PLAIN } from "@/lib/labels";
import { chf, groupDigits, parseAmount } from "@/lib/format";
import { useToast } from "@/components/Providers";

const TERMS = [12, 24, 36, 60, 84];
const AMOUNTS = ["100000", "250000", "500000", "1000000"];

function Wizard() {
  const router = useRouter(), toast = useToast();
  const draftId = useSearchParams().get("draft");
  const assess = useApi<any[]>("intelligence", "/v1/assessments");
  const catalogue = useApi<{ fields: { field: string; label: string; owner: string; default: boolean }[] }>("marketplace", "/v1/field-catalogue");
  const [step, setStep] = useState(0);
  const [amountText, setAmountText] = useState("300000"), [term, setTerm] = useState(60), [purpose, setPurpose] = useState(""), [collateral, setCollateral] = useState("");
  const [appId, setAppId] = useState<string | null>(draftId);
  const [chosen, setChosen] = useState<Set<string> | null>(null);
  const [preview, setPreview] = useState<any>(null), [err, setErr] = useState<any>(null), [done, setDone] = useState(false);
  const [agree, setAgree] = useState(false), [idem] = useState(newKey);
  useEffect(() => { window.scrollTo({ top: 0, behavior: "smooth" }); }, [step]);
  const amount = parseAmount(amountText);
  const latest = assess.data?.[0];

  useEffect(() => { if (!draftId) return; api("marketplace", `/v1/applications/${draftId}`).then((a) => { setAmountText(String(Math.round(Number(a.amount)))); setTerm(a.term_months); setPurpose(a.purpose ?? ""); setCollateral(a.collateral ?? ""); }).catch(() => {}); }, [draftId]);
  useEffect(() => { if (catalogue.data && !chosen) setChosen(new Set(catalogue.data.fields.filter((f) => f.default).map((f) => f.field))); }, [catalogue.data, chosen]);
  const available = useMemo(() => new Set((catalogue.data?.fields ?? []).map((f) => f.field)), [catalogue.data]);

  async function saveDraft() {
    setErr(null);
    if (!amount) { setErr({ detail: "Enter an amount, for example 300000 or 300k." }); return; }
    const body = { amount, term_months: term, purpose: purpose || null, collateral: collateral || null, assessment_id: latest?.id ?? null };
    try {
      if (appId) await api("marketplace", `/v1/applications/${appId}`, { method: "PATCH", body });
      else { const r = await api("marketplace", "/v1/applications", { method: "POST", body }); setAppId(r.id); }
      invalidate("marketplace"); setStep(1);
    } catch (e: any) { setErr(e); }
  }
  async function toPreview() {
    setErr(null);
    try { setPreview(await api("marketplace", `/v1/applications/${appId}/publication-preview?fields=${[...chosen!].join(",")}`)); setStep(2); }
    catch (e: any) { setErr(e); }
  }
  async function publish() {
    setErr(null);
    try { await api("marketplace", `/v1/applications/${appId}/publication`, { method: "POST", body: { fields: [...chosen!], assessment_id: preview?.assessment_id ?? latest?.id ?? null }, idem }); invalidate(); setDone(true); }
    catch (e: any) { setErr(e); }
  }
  const toggle = (f: string, on: boolean) => setChosen((c) => { const n = new Set(c); on ? n.add(f) : n.delete(f); return n; });

  if (done) return <div className="stack-l" style={{ paddingTop: 56 }}><Card><Success title="Your request is live" text="Matching lenders can now see what you chose to share. We will notify you when offers arrive."><Button href={`/sme/loans/${appId}`}>View request</Button></Success></Card></div>;
  return (
    <div className="stack-l">
      <PageHeader title="New request" back="/sme/loans" subtitle={["How much do you need?", "What may lenders see?", "Check and publish"][step]} />
      <Steps total={3} current={step} />
      <ErrorNote error={err} />

      {step === 0 && (
        <div className="stack-l enter">
          <Card className="stack">
            <label className="t-over" htmlFor="amount">Amount in CHF</label>
            <input id="amount" className="input-big" inputMode="decimal" autoFocus value={amountText} onChange={(e) => setAmountText(e.target.value)} onBlur={() => amount && setAmountText(groupDigits(amount))} aria-invalid={!amount} />
            <div className="hstack wrap">{AMOUNTS.map((a) => <button key={a} className="chip" aria-pressed={amount === a} onClick={() => setAmountText(groupDigits(a))}>{chf(a, { compact: true })}</button>)}</div>
          </Card>
          <Section title="For how long">
            <div className="hstack wrap">{TERMS.map((t) => <button key={t} className="chip" aria-pressed={term === t} onClick={() => setTerm(t)}>{t % 12 === 0 ? `${t / 12} year${t > 12 ? "s" : ""}` : `${t} months`}</button>)}</div>
          </Section>
          <Section title="Optional" footer="Lenders only see these if you tick them on the next step.">
            <List><Field label="Purpose"><input value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="New machine" maxLength={300} /></Field><Field label="Security"><input value={collateral} onChange={(e) => setCollateral(e.target.value)} placeholder="Equipment" maxLength={300} /></Field></List>
          </Section>
          <Button block onClick={saveDraft} disabled={!amount}>Continue</Button>
        </div>
      )}

      {step === 1 && (
        <div className="stack-l enter">
          <div className="banner info"><Tile name="lock" color="indigo" size="sm" /><div>You choose what lenders can see. Anything you leave off stays private, and you can stop sharing at any time.</div></div>
          {!chosen || !catalogue.data ? <Skeleton h={220} r={20} /> : FIELD_GROUPS.map((g) => {
            const fields = g.fields.filter((f) => available.has(f));
            if (!fields.length) return null;
            return (
              <Section key={g.title} title={g.title}>
                <List>{fields.map((f) => (
                  <Row key={f} noicon title={catalogue.data!.fields.find((x) => x.field === f)!.label} sub={FIELD_PLAIN[f]}>
                    <Switch checked={chosen.has(f)} onChange={(v) => toggle(f, v)} label={catalogue.data!.fields.find((x) => x.field === f)!.label} />
                  </Row>
                ))}</List>
              </Section>
            );
          })}
          <div className="hstack"><Button variant="secondary" onClick={() => setStep(0)}>Back</Button><div className="grow"><Button block onClick={toPreview} disabled={!chosen || chosen.size === 0}>Preview what lenders see</Button></div></div>
        </div>
      )}

      {step === 2 && preview && (
        <div className="stack-l enter">
          <Section title="Lenders will see" footer={`A snapshot of your figures as of ${preview.as_of}. If your numbers change later, you can publish again.`}>
            <List>{preview.fields.map((f: any) => <Row key={f.field} noicon title={f.label} value={<b style={{ color: "var(--label)" }}>{fmtPreview(f)}</b>} />)}</List>
          </Section>
          <Card className="stack-s">
            <div className="hstack"><Tile name="receipt" color="green" size="sm" /><b>Free to publish</b></div>
            <p className="muted">You only pay CredSort if a loan is funded. You will always see the fee before you choose an offer.</p>
          </Card>
          <Card className="hstack" style={{ alignItems: "flex-start" }}>
            <Switch checked={agree} onChange={setAgree} label="I agree to share these details" />
            <div className="grow">I agree to share exactly these details with lenders that match my request. I can stop sharing at any time.</div>
          </Card>
          <div className="hstack"><Button variant="secondary" onClick={() => setStep(1)}>Back</Button><div className="grow"><Button block onClick={publish} disabled={!agree}>Publish request</Button></div></div>
        </div>
      )}
    </div>
  );
}
function fmtPreview(f: { field: string; value: unknown }) {
  const v = f.value as any;
  if (["requested_amount", "revenue", "working_capital"].includes(f.field)) return chf(v);
  if (["revenue_growth", "ebitda_margin", "net_profit_margin", "equity_ratio"].includes(f.field)) return `${(Number(v) * 100).toFixed(1)}%`;
  if (["current_ratio", "debt_to_ebitda", "dscr"].includes(f.field)) return `${Number(v).toFixed(2)}×`;
  if (f.field === "term_months") return `${v} months`;
  return typeof v === "string" && !/\d/.test(v) ? v.charAt(0).toUpperCase() + v.slice(1).toLowerCase() : String(v ?? "n/a");
}
export default function NewLoan() { return <Suspense><Wizard /></Suspense>; }

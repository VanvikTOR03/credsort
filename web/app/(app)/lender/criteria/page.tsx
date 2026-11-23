"use client";
import { useEffect, useState } from "react";
import { api, invalidate, useApi } from "@/lib/client/api";
import { Button, Card, ErrorNote, Field, List, PageHeader, Section, Seg, Skeleton } from "@/components/ui";
import { useToast } from "@/components/Providers";

const INDUSTRIES = ["manufacturing", "hospitality", "software", "retail", "construction", "healthcare", "logistics", "services"];
const CATS = [{ value: "A", label: "A" }, { value: "B", label: "B" }, { value: "C", label: "C" }, { value: "D", label: "D" }];
const RANGE: { key: string; label: string; kind: "min" | "max"; hint: string }[] = [
  { key: "equity_ratio", label: "Equity ratio at least", kind: "min", hint: "0.25 means 25%" }, { key: "ebitda_margin", label: "EBITDA margin at least", kind: "min", hint: "0.08 means 8%" },
  { key: "dscr", label: "Debt service coverage at least", kind: "min", hint: "1.2 is common" }, { key: "debt_to_ebitda", label: "Debt / EBITDA at most", kind: "max", hint: "4 means four years" },
];
const WEIGHTS = [{ key: "assessment_score", label: "Overall score" }, { key: "equity_ratio", label: "Equity ratio" }, { key: "ebitda_margin", label: "EBITDA margin" }, { key: "debt_to_ebitda", label: "Debt / EBITDA" }, { key: "revenue_growth", label: "Revenue growth" }];

export default function Criteria() {
  const toast = useToast();
  const cur = useApi<{ version: number; criteria: any }>("marketplace", "/v1/lender/criteria");
  const [c, setC] = useState<any>(null), [more, setMore] = useState(false), [err, setErr] = useState<any>(null);
  useEffect(() => { if (cur.data && !c) setC({ industries: [], amount_min: "", amount_max: "", min_assessment_category: "C", min: {}, max: {}, weights: {}, ...cur.data.criteria }); }, [cur.data, c]);
  if (!c) return <div className="stack-l"><PageHeader title="Criteria" /><Skeleton h={260} r={20} /></div>;
  const set = (k: string, v: any) => setC({ ...c, [k]: v });
  const setRange = (kind: "min" | "max", k: string, v: string) => setC({ ...c, [kind]: { ...c[kind], [k]: v } });
  async function save() {
    setErr(null);
    const clean: any = { min_assessment_category: c.min_assessment_category };
    if (c.industries.length) clean.industries = c.industries;
    if (c.amount_min) clean.amount_min = String(c.amount_min); if (c.amount_max) clean.amount_max = String(c.amount_max);
    for (const kind of ["min", "max"] as const) { const o = Object.fromEntries(Object.entries(c[kind] ?? {}).filter(([, v]) => v !== "" && v !== undefined)); if (Object.keys(o).length) clean[kind] = o; }
    const w = Object.fromEntries(Object.entries(c.weights ?? {}).filter(([, v]) => Number(v) > 0)); if (Object.keys(w).length) clean.weights = w;
    try { await api("marketplace", "/v1/lender/criteria", { method: "PUT", body: { criteria: clean } }); invalidate(); toast("Criteria saved. Matches update now."); } catch (e: any) { setErr(e); }
  }
  return (
    <div className="stack-l">
      <PageHeader title="Criteria" />
      <Section title="Loan size (CHF)"><List><Field label="From"><input inputMode="numeric" value={c.amount_min ?? ""} onChange={(e) => set("amount_min", e.target.value.replace(/[^\d]/g, ""))} placeholder="100000" /></Field><Field label="To"><input inputMode="numeric" value={c.amount_max ?? ""} onChange={(e) => set("amount_max", e.target.value.replace(/[^\d]/g, ""))} placeholder="No limit" /></Field></List></Section>
      <Section title="Lowest category you accept"><div className="center"><Seg label="Lowest category" options={CATS} value={c.min_assessment_category} onChange={(v) => set("min_assessment_category", v)} /></div><p className="t-foot center" style={{ marginTop: 8 }}>A is strongest. {c.min_assessment_category} or better will match.</p></Section>
      <Section title="Industries">
        <div className="hstack wrap">{INDUSTRIES.map((i) => <button key={i} className="chip" aria-pressed={c.industries.includes(i)} onClick={() => set("industries", c.industries.includes(i) ? c.industries.filter((x: string) => x !== i) : [...c.industries, i])}>{i[0].toUpperCase() + i.slice(1)}</button>)}</div>
      </Section>
      <Button variant="secondary" onClick={() => setMore(!more)}>{more ? "Hide" : "Show"} more filters</Button>
      {more && (
        <div className="stack-l enter">
          <Section title="Financial limits"><List>{RANGE.map((r) => <Field key={r.key} label={r.label} hint={r.hint}><input inputMode="decimal" value={c[r.kind]?.[r.key] ?? ""} onChange={(e) => setRange(r.kind, r.key, e.target.value)} placeholder="Any" /></Field>)}</List></Section>
          <Section title="What matters most">
            <Card className="stack">{WEIGHTS.map((w) => <div key={w.key} className="stack-s"><div className="hstack spread"><label>{w.label}</label><b className="num">{c.weights?.[w.key] ?? 0}</b></div><input type="range" min={0} max={5} step={1} value={c.weights?.[w.key] ?? 0} onChange={(e) => set("weights", { ...c.weights, [w.key]: Number(e.target.value) })} aria-label={w.label} /></div>)}</Card>
          </Section>
        </div>
      )}
      <ErrorNote error={err} />
      <Button block onClick={save}>Save criteria</Button>
    </div>
  );
}

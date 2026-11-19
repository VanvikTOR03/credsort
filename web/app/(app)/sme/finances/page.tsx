"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, invalidate, newKey, useApi } from "@/lib/client/api";
import { Button, Card, Empty, ErrorNote, List, ListSkeleton, Meter, PageHeader, Pill, Ring, Row, Section, Seg, Sheet, Skeleton } from "@/components/ui";
import { Icon, Tile } from "@/components/Icon";
import { useToast } from "@/components/Providers";
import { CATEGORY, METRIC_GROUPS, METRIC_HELP, fmtMetric } from "@/lib/labels";
import { ago, chf, date } from "@/lib/format";

type Tab = "score" | "whatif" | "data";

function Inner() {
  const q = useSearchParams(), router = useRouter();
  const tab = (q.get("tab") as Tab) || "score";
  const setTab = (t: Tab) => router.replace(t === "score" ? "/sme/finances" : `/sme/finances?tab=${t}`, { scroll: false });
  return (
    <div className="stack-l">
      <PageHeader title="Finances" subtitle="Your numbers, your score, your what-ifs." />
      <div className="center"><Seg label="Finance sections" value={tab} onChange={setTab} options={[{ value: "score", label: "Score" }, { value: "whatif", label: "What-if" }, { value: "data", label: "Data" }]} /></div>
      {tab === "score" && <ScoreTab goData={() => setTab("data")} />}
      {tab === "whatif" && <WhatIfTab />}
      {tab === "data" && <DataTab />}
    </div>
  );
}
export default function Finances() { return <Suspense><Inner /></Suspense>; }

/* ---------------- Score ---------------- */
function ScoreTab({ goData }: { goData: () => void }) {
  const list = useApi<any[]>("intelligence", "/v1/assessments");
  const id = list.data?.[0]?.id;
  const detail = useApi<any>("intelligence", id ? `/v1/assessments/${id}` : null);
  const explain = useApi<any>("advisory", id ? `/v1/assessments/${id}/explanation` : null);
  const [open, setOpen] = useState<string | null>(null);

  if (list.loading) return <div className="stack"><Skeleton h={190} r={20} /><ListSkeleton rows={4} /></div>;
  if (!id) return <Card><Empty icon="plug" color="accent" title="No numbers yet" text="Connect your accounting and we will calculate your score within seconds." action={<Button onClick={goData}>Connect accounting</Button>} /></Card>;
  const a = detail.data?.assessment;
  const metrics: any[] = detail.data?.metrics ?? [];
  const byCode = Object.fromEntries(metrics.map((m) => [m.code, m]));
  return (
    <div className="stack-l">
      {!a ? <Skeleton h={190} r={20} /> : (
        <Card className="enter stack">
          <div className="hstack" style={{ gap: 20 }}>
            <Ring value={a.score} size={132} stroke={13} color={CATEGORY[a.category]?.color}>
              <div className="num" style={{ fontSize: 38, fontWeight: 750, letterSpacing: "-.03em", lineHeight: 1 }}>{a.score}</div><div className="t-cap">of 100</div>
            </Ring>
            <div className="stack-s grow">
              <div className="t-over">Category</div>
              <div className="t-large" style={{ fontSize: 30 }}>{a.category} · {a.label}</div>
              <div className="hstack wrap" style={{ gap: 6 }}><Pill tone={a.confidence.band === "HIGH" ? "green" : a.confidence.band === "MEDIUM" ? "orange" : "red"}>Data confidence: {a.confidence.band.toLowerCase()}</Pill>{a.confidence.demo_data && <Pill>Demo data</Pill>}</div>
            </div>
          </div>
          <p className="t-foot">{a.disclaimer} As of {date(detail.data.snapshot.period_end)}.</p>
        </Card>
      )}

      {explain.data && (
        <Card className="stack-s enter" style={{ "--i": 1 } as any}>
          <div className="hstack"><Tile name="spark" color="purple" size="sm" /><div className="t-head">What this means</div></div>
          <p>{explain.data.summary}</p>
          {explain.data.strengths?.length > 0 && <div className="stack-s"><div className="t-over">Working in your favour</div>{explain.data.strengths.slice(0, 3).map((s: string) => <div className="hstack" key={s} style={{ alignItems: "flex-start", gap: 10 }}><span className="tile xs c-green"><Icon name="check" /></span><span>{s}</span></div>)}</div>}
          {explain.data.concerns?.length > 0 && <div className="stack-s"><div className="t-over">Worth watching</div>{explain.data.concerns.map((s: string) => <div className="hstack" key={s} style={{ alignItems: "flex-start", gap: 10 }}><span className="tile xs c-orange"><Icon name="warning" /></span><span>{s}</span></div>)}</div>}
          {explain.data.suggestions?.length > 0 && <div className="stack-s"><div className="t-over">Ideas</div>{explain.data.suggestions.map((s: string) => <div key={s}>{s}</div>)}</div>}
          <p className="t-cap">{explain.data.disclaimer}</p>
        </Card>
      )}

      {a && (
        <Section title="What drives your score" footer="Tap a row to see what it means.">
          <List>
            {a.factors.map((f: any) => (
              <button className="row noicon" key={f.code} onClick={() => setOpen(f.code)} style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
                <div className="hstack spread"><span className="title">{f.label}</span><span className="num muted">{fmtMetric(f.code, "RATIO", f.value)}</span></div>
                <Meter value={f.points} label={`${f.label}: ${f.points} of 100`} />
              </button>
            ))}
          </List>
        </Section>
      )}

      {METRIC_GROUPS.map((g) => (
        <Section key={g.title} title={g.title}>
          <List>{g.codes.filter((c) => byCode[c]).map((c) => (
            <Row key={c} icon={g.icon} color={g.color} title={byCode[c].label} sub={METRIC_HELP[c]} value={<b style={{ color: "var(--label)" }}>{byCode[c].status === "OK" ? fmtMetric(c, byCode[c].unit, byCode[c].value) : "n/a"}</b>} />
          ))}</List>
        </Section>
      ))}
      <Sheet open={!!open} onClose={() => setOpen(null)} title={a?.factors.find((f: any) => f.code === open)?.label}>
        {open && <div className="stack"><p>{METRIC_HELP[open]}</p><Button block variant="secondary" onClick={() => setOpen(null)}>Got it</Button></div>}
      </Sheet>
    </div>
  );
}

/* ---------------- What-if ---------------- */
function WhatIfTab() {
  const list = useApi<any[]>("intelligence", "/v1/assessments");
  const id = list.data?.[0]?.id;
  const [rev, setRev] = useState(0), [cost, setCost] = useState(0), [debt, setDebt] = useState(0);
  const [res, setRes] = useState<any>(null), [busy, setBusy] = useState(false), [err, setErr] = useState<any>(null);
  const explain = useApi<any>("advisory", res ? `/v1/scenarios/${res.id}/explanation` : null);
  useEffect(() => {
    if (!id) return;
    const t = setTimeout(async () => {
      setBusy(true); setErr(null);
      try {
        const inputs: Record<string, string> = {};
        if (rev !== 0) inputs.revenue_change_pct = String(rev);
        if (cost > 0) inputs.cost_reduction_pct = String(cost);
        if (debt > 0) inputs.debt_repayment_from_cash = String(debt);
        setRes(await api("intelligence", "/v1/scenarios", { method: "POST", body: { assessment_id: id, inputs } }));
      } catch (e) { setErr(e); } finally { setBusy(false); }
    }, 350);
    return () => clearTimeout(t);
  }, [id, rev, cost, debt]);

  if (list.loading) return <Skeleton h={300} r={20} />;
  if (!id) return <Card><Empty icon="sliders" color="indigo" title="Nothing to play with yet" text="Connect your accounting first. Then you can see how changes would move your score." /></Card>;
  const b = res?.before.assessment, a = res?.after.assessment;
  const delta = a && b ? a.score - b.score : 0;
  const slider = (label: string, v: number, set: (n: number) => void, min: number, max: number, step: number, unit: string) => (
    <div className="stack-s"><div className="hstack spread"><label className="title">{label}</label><b className="num" style={{ color: v ? "var(--accent)" : undefined }}>{v > 0 && unit === "%" && label.startsWith("Sales") ? "+" : ""}{unit === "CHF" ? chf(v) : `${v}%`}</b></div>
      <input type="range" min={min} max={max} step={step} value={v} onChange={(e) => set(Number(e.target.value))} aria-label={label} /></div>
  );
  return (
    <div className="stack-l">
      <Card className="stack enter">
        {slider("Sales change", rev, setRev, -30, 30, 1, "%")}
        {slider("Cost reduction", cost, setCost, 0, 20, 1, "%")}
        {slider("Pay down debt from cash", debt, setDebt, 0, 200000, 5000, "CHF")}
        <div className="hstack spread"><span className="t-foot">Nothing is saved. This is an estimate, not a promise.</span>{(rev || cost || debt) ? <Button size="sm" variant="plain" onClick={() => { setRev(0); setCost(0); setDebt(0); }}>Reset</Button> : null}</div>
      </Card>
      <ErrorNote error={err} />
      {a && b && (
        <Card className="stack enter" style={{ "--i": 1, opacity: busy ? .6 : 1, transition: "opacity .2s" } as any}>
          <div className="hstack" style={{ justifyContent: "space-around" }}>
            <div className="center"><div className="t-over">Now</div><div className="num t-large">{b.score}</div><Pill>{b.category}</Pill></div>
            <Tile name="arrow" color={delta >= 0 ? "green" : "red"} />
            <div className="center"><div className="t-over">After</div><div className="num t-large" style={{ color: delta > 0 ? "var(--green)" : delta < 0 ? "var(--red)" : undefined }}>{a.score}</div><Pill tone={a.category !== b.category ? (delta > 0 ? "green" : "red") : undefined}>{a.category}</Pill></div>
          </div>
          <p className="center muted">{delta === 0 ? "No change in your score." : `${delta > 0 ? "Up" : "Down"} ${Math.abs(delta)} point${Math.abs(delta) === 1 ? "" : "s"}.`}</p>
          <div className="list">{res.after.metrics.filter((m: any) => ["ebitda_margin", "equity_ratio", "debt_to_ebitda", "dscr"].includes(m.code)).map((m: any) => {
            const was = res.before.metrics.find((x: any) => x.code === m.code);
            return <Row key={m.code} noicon title={m.code === "ebitda_margin" ? "EBITDA margin" : m.code === "equity_ratio" ? "Equity ratio" : m.code === "debt_to_ebitda" ? "Debt / EBITDA" : "Debt service coverage"} value={<span><span className="muted">{fmtMetric(m.code, m.unit, was?.value)}</span> → <b style={{ color: "var(--label)" }}>{fmtMetric(m.code, m.unit, m.value)}</b></span>} />;
          })}</div>
        </Card>
      )}
      {explain.data && <Card className="stack-s"><div className="hstack"><Tile name="spark" color="purple" size="sm" /><div className="t-head">What changes</div></div><p>{explain.data.summary}</p>{explain.data.suggestions?.map((s: string) => <p key={s} className="muted">{s}</p>)}</Card>}
      {res?.assumptions && <Section title="Assumptions"><Card className="stack-s">{res.assumptions.map((s: string) => <p key={s} className="t-foot">{s}</p>)}</Card></Section>}
    </div>
  );
}

/* ---------------- Data ---------------- */
const DATASETS = [{ value: "muster", label: "Manufacturer" }, { value: "alpina", label: "Restaurant" }, { value: "pixelwerk", label: "Software" }];
function DataTab() {
  const toast = useToast();
  const q = useSearchParams();
  const conns = useApi<any[]>("accounting", "/v1/connections");
  const jobs = useApi<any[]>("accounting", "/v1/import-jobs", { refresh: 2500 });
  const [sheet, setSheet] = useState(false), [dataset, setDataset] = useState("muster"), [err, setErr] = useState<any>(null);
  useEffect(() => { if (q.get("bexio") === "connected") toast("bexio connected"); if (q.get("bexio") === "failed") toast("bexio could not be connected", "error"); }, []); // eslint-disable-line

  async function connectDemo() {
    setErr(null);
    try {
      const c = await api("accounting", "/v1/connections", { method: "POST", body: { source_type: "SYNTHETIC", dataset } });
      await api("accounting", "/v1/import-jobs", { method: "POST", body: { connection_id: c.id } });
      invalidate(); setSheet(false); toast("Importing demo data");
    } catch (e: any) { setErr(e); }
  }
  async function connectBexio() {
    try { const r = await api("accounting", "/v1/connections/bexio/authorize"); location.href = r.url; }
    catch (e: any) { toast(e.code === "bexio_not_configured" ? "bexio is not set up on this server yet" : e.detail, "error"); }
  }
  const running = jobs.data?.find((j) => ["QUEUED", "RUNNING"].includes(j.status));
  return (
    <div className="stack-l">
      {running && <Card className="stack-s enter"><div className="hstack spread"><b>Importing your numbers</b><span className="t-foot num">{running.progress}%</span></div><Meter value={running.progress} label="Import progress" /><p className="t-foot">You can leave this page. We will let you know when your score is ready.</p></Card>}
      <Section title="Connected sources">
        {conns.loading ? <ListSkeleton rows={1} /> : conns.data?.length ? (
          <List>{conns.data.map((c) => (
            <Row key={c.id} icon={c.source_type === "BEXIO" ? "plug" : "doc"} color={c.source_type === "BEXIO" ? "blue" : "gray"} title={c.source_type === "BEXIO" ? "bexio" : "Demo data"}
              sub={c.last_import_at ? `Last import ${ago(c.last_import_at)} · figures to ${date(c.last_period_end)}` : "No import yet"} value={<Pill tone={c.status === "ACTIVE" ? "green" : "orange"}>{c.status === "ACTIVE" ? "Connected" : "Disconnected"}</Pill>}>
              {c.status === "ACTIVE" && <Button size="sm" variant="secondary" onClick={async () => { await api("accounting", "/v1/import-jobs", { method: "POST", body: { connection_id: c.id } }); invalidate(); toast("Refreshing your numbers"); }}>Refresh</Button>}
            </Row>
          ))}</List>
        ) : <Card><Empty icon="plug" color="accent" title="Connect your accounting" text="We read your numbers once, check them, and keep them private until you choose who sees what." /></Card>}
      </Section>
      <Section title="Add a source" footer="We only read figures. We cannot change anything in your books, and you can disconnect at any time.">
        <List>
          <Row icon="plug" color="blue" title="bexio" sub="Connect your real accounting" onClick={connectBexio} />
          <Row icon="doc" color="gray" title="Try demo data" sub="Explore CredSort with a sample company" onClick={() => setSheet(true)} />
        </List>
      </Section>
      {!!jobs.data?.length && (
        <Section title="Recent imports"><List>{jobs.data.slice(0, 4).map((j) => (
          <Row key={j.id} icon={j.status === "COMPLETED" ? "check" : j.status === "FAILED" ? "warning" : "refresh"} color={j.status === "COMPLETED" ? "green" : j.status === "FAILED" ? "red" : "blue"} title={j.status === "COMPLETED" ? "Import finished" : j.status === "FAILED" ? "Import failed" : "Import running"} sub={j.failure_reason ?? ago(j.finished_at ?? j.created_at)} />
        ))}</List></Section>
      )}
      <Sheet open={sheet} onClose={() => setSheet(false)} title="Choose a sample company">
        <div className="stack">
          <div className="hstack wrap">{DATASETS.map((d) => <button key={d.value} className="chip" aria-pressed={dataset === d.value} onClick={() => setDataset(d.value)}>{d.label}</button>)}</div>
          <p className="muted">Synthetic numbers for a typical Swiss company. Everything is labelled as demo data.</p>
          <ErrorNote error={err} />
          <Button block onClick={connectDemo}>Import demo data</Button>
        </div>
      </Sheet>
    </div>
  );
}

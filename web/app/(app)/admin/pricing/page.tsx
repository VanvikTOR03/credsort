"use client";
import { useState } from "react";
import { api, invalidate, useApi } from "@/lib/client/api";
import { Button, Card, ErrorNote, Field, List, ListSkeleton, PageHeader, Pill, Row, Section, Sheet } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { chf, date } from "@/lib/format";

export default function Pricing() {
  const toast = useToast();
  const books = useApi<any[]>("billing", "/v1/admin/price-books");
  const [open, setOpen] = useState(false), [err, setErr] = useState<any>(null);
  const [f, setF] = useState({ smePct: "1.0", smeMin: "1000", smeCap: "8000", lenPct: "0.75", lenMin: "2000", lenCap: "7500", placeholder: true });
  async function create() {
    setErr(null);
    const rule = (code: string, payer: string, p: string, min: string, cap: string) => ({ code, payer, trigger: "LOAN_FUNDED", calculator: "PERCENT_OF_PRINCIPAL", percent: p, min_amount: min, cap_amount: cap });
    try { await api("billing", "/v1/admin/price-books", { method: "POST", body: { placeholder: f.placeholder, rules: [rule("SME_SUCCESS", "SME", f.smePct, f.smeMin, f.smeCap), rule("LENDER_SUCCESS", "LENDER", f.lenPct, f.lenMin, f.lenCap)] } }); invalidate(); setOpen(false); toast("Draft price book created"); } catch (e: any) { setErr(e); }
  }
  async function activate(id: string) { try { await api("billing", `/v1/admin/price-books/${id}/activate`, { method: "POST", body: {} }); invalidate(); toast("Price book activated"); } catch (e: any) { toast(e.detail, "error"); } }
  return (
    <div className="stack-l">
      <PageHeader title="Pricing" subtitle="Price books are versioned. Active ones never change." actions={<Button size="sm" icon="plus" onClick={() => setOpen(true)}>New</Button>} />
      {books.loading ? <ListSkeleton rows={2} /> : <div className="stack">{(books.data ?? []).map((b) => (
        <Card key={b.id} className="stack enter">
          <div className="hstack spread"><b className="t-head">Version {b.version}</b><span className="hstack" style={{ gap: 6 }}>{b.is_placeholder && <Pill tone="orange">Demo prices</Pill>}<Pill tone={b.status === "ACTIVE" ? "green" : b.status === "DRAFT" ? "blue" : undefined}>{b.status.toLowerCase()}</Pill></span></div>
          <List>{b.rules.map((r: any) => <Row key={r.code} noicon title={`${r.payer === "SME" ? "Company" : "Lender"} success fee`} sub={`${Number(r.percent)}% of the loan, min ${chf(r.min_amount)}, max ${chf(r.cap_amount)}`} />)}</List>
          <div className="t-foot">Effective from {date(b.effective_from)} · fiduciary referral share {Number(b.referral_percent)}%</div>
          {b.status === "DRAFT" && <Button onClick={() => activate(b.id)}>Activate</Button>}
        </Card>))}</div>}
      <Sheet open={open} onClose={() => setOpen(false)} title="New price book">
        <div className="stack">
          <p className="muted">Fees are charged only when a loan is funded. A new book stays a draft until you activate it.</p>
          <List><Field label="Company %"><input inputMode="decimal" value={f.smePct} onChange={(e) => setF({ ...f, smePct: e.target.value })} /></Field><Field label="Company min"><input inputMode="decimal" value={f.smeMin} onChange={(e) => setF({ ...f, smeMin: e.target.value })} /></Field><Field label="Company max"><input inputMode="decimal" value={f.smeCap} onChange={(e) => setF({ ...f, smeCap: e.target.value })} /></Field></List>
          <List><Field label="Lender %"><input inputMode="decimal" value={f.lenPct} onChange={(e) => setF({ ...f, lenPct: e.target.value })} /></Field><Field label="Lender min"><input inputMode="decimal" value={f.lenMin} onChange={(e) => setF({ ...f, lenMin: e.target.value })} /></Field><Field label="Lender max"><input inputMode="decimal" value={f.lenCap} onChange={(e) => setF({ ...f, lenCap: e.target.value })} /></Field></List>
          <ErrorNote error={err} /><Button block onClick={create}>Create draft</Button>
        </div>
      </Sheet>
    </div>
  );
}

"use client";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { api, invalidate, newKey, useApi } from "@/lib/client/api";
import { Button, Card, Empty, ErrorNote, List, PageHeader, Pill, Row, Section, Sheet, Skeleton, Success } from "@/components/ui";
import { Icon, Tile } from "@/components/Icon";
import { useToast } from "@/components/Providers";
import { APP_STATUS, OFFER_STATUS, REPAYMENT } from "@/lib/labels";
import { chf, date, daysLeft, ratePct } from "@/lib/format";

export default function LoanDetail() {
  const { id } = useParams<{ id: string }>(), router = useRouter(), toast = useToast();
  const app = useApi<any>("marketplace", `/v1/applications/${id}`, { refresh: 8000 });
  const offers = useApi<any[]>("marketplace", `/v1/applications/${id}/offers`, { refresh: 8000 });
  const [pick, setPick] = useState<any>(null), [dispute, setDispute] = useState(false), [withdraw, setWithdraw] = useState(false), [err, setErr] = useState<any>(null), [chosenDone, setChosenDone] = useState(false);
  const a = app.data;
  const sorted = useMemo(() => [...(offers.data ?? [])].sort((x, y) => Number(x.cost?.total ?? 1e18) - Number(y.cost?.total ?? 1e18)), [offers.data]);
  const open = sorted.filter((o) => o.status === "SUBMITTED");
  const live = sorted.find((o) => ["SELECTED", "FUNDED", "DISPUTED"].includes(o.status));

  async function select() {
    setErr(null);
    try { await api("marketplace", `/v1/offers/${pick.id}/selection`, { method: "POST", idem: newKey() }); invalidate(); setPick(null); setChosenDone(true); window.scrollTo({ top: 0, behavior: "smooth" }); }
    catch (e: any) { setErr(e); }
  }
  async function raise() { setErr(null); try { await api("marketplace", `/v1/applications/${id}/dispute`, { method: "POST" }); invalidate(); setDispute(false); toast("We have paused the fee and told your lender"); } catch (e: any) { setErr(e); } }
  async function withdrawApp() { setErr(null); try { await api("marketplace", `/v1/applications/${id}/withdraw`, { method: "POST" }); invalidate(); router.push("/sme/loans"); toast("Request withdrawn"); } catch (e: any) { setErr(e); } }

  if (app.loading) return <div className="stack-l"><PageHeader title="Loan" back="/sme/loans" /><Skeleton h={160} r={20} /></div>;
  if (!a) return <div className="stack-l"><PageHeader title="Loan" back="/sme/loans" /><ErrorNote error={app.error} retry={app.reload} /></div>;
  const st = APP_STATUS[a.status] ?? { label: a.status, tone: undefined };
  const stages = ["Requested", "Visible to lenders", "Offer chosen", "Funded"];
  const stageIdx = a.status === "DRAFT" ? 0 : a.status === "PUBLISHED" ? 1 : a.status === "OFFER_SELECTED" ? 2 : ["FUNDED", "DISPUTED", "CLOSED"].includes(a.status) ? 3 : 1;

  return (
    <div className="stack-l">
      <PageHeader title={chf(a.amount)} back="/sme/loans" subtitle={<span className="hstack wrap" style={{ gap: 8 }}><Pill tone={st.tone}>{st.label}</Pill><span>{a.term_months} months{a.purpose ? ` · ${a.purpose}` : ""}</span></span>} />
      <ErrorNote error={err} />

      {chosenDone && <Card><Success title="Offer chosen" text="We told your lender. Once they confirm the payout, the loan is complete."><Button variant="secondary" onClick={() => setChosenDone(false)}>Continue</Button></Success></Card>}

      {!chosenDone && a.status === "FUNDED" && (
        <div className="banner info enter"><Tile name="calendar" color="blue" size="sm" /><div className="grow"><b>Payout confirmed {date(a.funded_at)}</b><div className="t-cap">You have {daysLeft(a.dispute_until)} more days to raise a problem if the money did not arrive.</div></div><Button size="sm" variant="danger-soft" onClick={() => setDispute(true)}>Raise a problem</Button></div>
      )}
      {a.status === "DISPUTED" && <div className="banner enter"><Tile name="warning" color="orange" size="sm" /><div><b>Your problem was reported</b><div className="t-cap">The CredSort fee is on hold while this is looked into.</div></div></div>}
      {a.status === "DRAFT" && <Card className="stack"><p>This request is a draft. Lenders cannot see it yet.</p><Button href={`/sme/loans/new?draft=${a.id}`}>Continue</Button></Card>}

      <Card className="enter">
        <div className="timeline">
          {stages.map((s, i) => <div className="item" key={s}><span className="dot" style={{ background: i <= stageIdx ? "var(--accent)" : "var(--surface)", borderColor: i <= stageIdx ? "var(--accent)" : "var(--fill)" }} /><div style={{ fontWeight: i === stageIdx ? 650 : 500, color: i <= stageIdx ? "var(--label)" : "var(--label-3)" }}>{s}</div></div>)}
        </div>
      </Card>

      {live && (
        <Section title="Your chosen offer"><OfferCard o={live} /></Section>
      )}

      {a.status === "PUBLISHED" && (
        <Section title={open.length ? "Compare offers" : "Offers"} footer={open.length ? "Sorted by total cost, lowest first. Total cost = interest + lender fees + CredSort fee. You pay the CredSort fee only if the loan is funded." : undefined}>
          {offers.loading ? <Skeleton h={180} r={20} /> : open.length === 0 ? <Card><Empty icon="clock" color="blue" title="No offers yet" text="Matching lenders are reviewing your request. We will notify you as soon as one arrives." /></Card> : (
            <div className="stack">{open.map((o, i) => <OfferCard key={o.id} o={o} best={i === 0 && open.length > 1} action={<Button block onClick={() => setPick(o)}>Choose this offer</Button>} i={i} />)}</div>
          )}
        </Section>
      )}

      {a.status === "PUBLISHED" && <List><Row icon="shield" color="indigo" href="/sme/privacy" title="Who can see this request" sub="Manage sharing at any time" /></List>}
      {(a.status === "PUBLISHED" || a.status === "DRAFT") && <div className="center"><Button variant="plain" onClick={() => setWithdraw(true)}>Withdraw request</Button></div>}

      <Sheet open={!!pick} onClose={() => setPick(null)} title="Choose this offer?">
        {pick && <div className="stack">
          <dl className="kv"><dt>Lender</dt><dd>{pick.lender_name}</dd><dt>Amount</dt><dd>{chf(pick.amount)}</dd><dt>Interest rate</dt><dd>{ratePct(pick.rate)} a year</dd><dt>Total cost</dt><dd>{chf(pick.cost.total)}</dd></dl>
          <p className="muted">{pick.credsort_fee?.pricing === "PRICED" ? `CredSort charges ${chf(pick.credsort_fee.amount)} only if this loan is funded. That price is locked now.` : "The CredSort fee is still to be confirmed. You pay nothing unless the loan is funded."} Other offers are closed once you choose.</p>
          <ErrorNote error={err} />
          <Button block onClick={select}>Yes, choose this offer</Button><Button block variant="plain" onClick={() => setPick(null)}>Not yet</Button>
        </div>}
      </Sheet>
      <Sheet open={dispute} onClose={() => setDispute(false)} title="Did the money not arrive?">
        <div className="stack"><p>We will pause the CredSort fee and tell your lender. Only continue if you did not receive the loan amount.</p><ErrorNote error={err} /><Button block variant="danger" onClick={raise}>Report a problem</Button><Button block variant="plain" onClick={() => setDispute(false)}>Cancel</Button></div>
      </Sheet>
      <Sheet open={withdraw} onClose={() => setWithdraw(false)} title="Withdraw this request?">
        <div className="stack"><p>Lenders will no longer see it and open offers are closed.</p><Button block variant="danger" onClick={withdrawApp}>Withdraw</Button><Button block variant="plain" onClick={() => setWithdraw(false)}>Keep it</Button></div>
      </Sheet>
    </div>
  );
}

function OfferCard({ o, best, action, i = 0 }: { o: any; best?: boolean; action?: React.ReactNode; i?: number }) {
  const st = OFFER_STATUS[o.status] ?? { label: o.status, tone: undefined };
  return (
    <Card className="stack enter" style={{ "--i": i, outline: best ? "2px solid var(--accent)" : undefined } as any}>
      <div className="hstack spread"><div className="hstack"><Tile name="bank" color="indigo" size="sm" /><b className="t-head">{o.lender_name}</b></div><span className="hstack" style={{ gap: 6 }}>{best && <Pill tone="accent">Lowest total cost</Pill>}{o.status !== "SUBMITTED" && <Pill tone={st.tone}>{st.label}</Pill>}</span></div>
      <div className="grid c3" style={{ gap: 10 }}>
        <div className="stat"><span className="v">{ratePct(o.rate)}</span><span className="l">per year</span></div>
        <div className="stat"><span className="v">{chf(o.amount, { compact: true })}</span><span className="l">{o.term_months} months</span></div>
        <div className="stat"><span className="v">{chf(o.cost?.total, { compact: true })}</span><span className="l">total cost</span></div>
      </div>
      <dl className="kv t-foot"><dt>Interest over the term</dt><dd>{chf(o.cost?.interest)}</dd><dt>Lender fees</dt><dd>{chf(o.cost?.lender_fees)}</dd>
        <dt>CredSort fee (only if funded)</dt><dd>{o.credsort_fee?.pricing === "PRICED" ? chf(o.credsort_fee.amount) : "To be confirmed"}</dd>
        <dt>Repayment</dt><dd>{REPAYMENT[o.repayment] ?? o.repayment}</dd>{o.collateral && <><dt>Security</dt><dd>{o.collateral}</dd></>}
        {o.status === "SUBMITTED" && <><dt>Valid until</dt><dd>{date(o.valid_until)}</dd></>}</dl>
      {action}
    </Card>
  );
}

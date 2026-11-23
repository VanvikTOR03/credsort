"use client";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api, invalidate, newKey, useApi } from "@/lib/client/api";
import { Button, Card, Empty, ErrorNote, PageHeader, Pill, Sheet, Skeleton, Success } from "@/components/ui";
import { Icon } from "@/components/Icon";
import { useToast } from "@/components/Providers";
import { APP_STATUS, OFFER_STATUS, REPAYMENT } from "@/lib/labels";
import { chf, date, daysLeft, ratePct } from "@/lib/format";
import { fairRange, fairTag, fmtRange, monthlyAnnuity } from "@/lib/loan";

export default function LoanDetail() {
  const { id } = useParams<{ id: string }>(), router = useRouter(), toast = useToast();
  const app = useApi<any>("marketplace", `/v1/applications/${id}`, { refresh: 6000 });
  const offers = useApi<any[]>("marketplace", `/v1/applications/${id}/offers`, { refresh: 6000 });
  const assess = useApi<any[]>("intelligence", "/v1/assessments");
  const price = useApi<any>("billing", "/v1/unlock/price");
  const [pick, setPick] = useState<any>(null), [detail, setDetail] = useState<any>(null), [dispute, setDispute] = useState(false), [withdraw, setWithdraw] = useState(false);
  const [err, setErr] = useState<any>(null), [chosenDone, setChosenDone] = useState(false);
  const a = app.data;
  const assessment = assess.data?.find((x) => x.id === a?.assessment_id) ?? assess.data?.[0];
  const range = fairRange(assessment?.category);
  const sorted = useMemo(() => [...(offers.data ?? [])].sort((x, y) => Number(x.cost?.total ?? 1e18) - Number(y.cost?.total ?? 1e18)), [offers.data]);
  const open = sorted.filter((o) => o.status === "SUBMITTED");
  const live = sorted.find((o) => ["SELECTED", "FUNDED", "DISPUTED"].includes(o.status));
  const unlocked = !!a?.unlocked_at || (offers.data?.[0]?.unlocked ?? false);

  // The checkout runs in its own window and reports back. If the browser blocks the window we fall back to a full-page checkout.
  useEffect(() => {
    const onMsg = (e: MessageEvent) => {
      if (e.origin !== location.origin || e.data?.type !== "credsort:paid") return;
      invalidate(); toast("Offers unlocked");
      const t = setInterval(() => invalidate("marketplace"), 1000); setTimeout(() => clearInterval(t), 6000);
    };
    window.addEventListener("message", onMsg); return () => window.removeEventListener("message", onMsg);
  }, [toast]);
  function checkout() {
    const w = window.open(`/pay/${id}`, "credsort-pay", "popup=yes,width=480,height=780");
    if (!w) location.href = `/pay/${id}?return=1`;
  }

  async function select() {
    setErr(null);
    try { await api("marketplace", `/v1/offers/${pick.id}/selection`, { method: "POST", idem: newKey() }); invalidate(); setPick(null); setDetail(null); setChosenDone(true); window.scrollTo({ top: 0 }); }
    catch (e: any) { setErr(e); }
  }
  async function raise() { setErr(null); try { await api("marketplace", `/v1/applications/${id}/dispute`, { method: "POST" }); invalidate(); setDispute(false); toast("Reported"); } catch (e: any) { setErr(e); } }
  async function withdrawApp() { setErr(null); try { await api("marketplace", `/v1/applications/${id}/withdraw`, { method: "POST" }); invalidate(); router.push("/sme/loans"); } catch (e: any) { setErr(e); } }

  if (app.loading) return <div><PageHeader title="Loan" back="/sme/loans" /><Skeleton h={160} r={6} /></div>;
  if (!a) return <div><PageHeader title="Loan" back="/sme/loans" /><ErrorNote error={app.error} retry={app.reload} /></div>;
  const st = APP_STATUS[a.status] ?? { label: a.status, tone: undefined };
  const stages = ["Requested", "Visible", "Chosen", "Funded"];
  const stageIdx = a.status === "DRAFT" ? 0 : a.status === "PUBLISHED" ? 1 : a.status === "OFFER_SELECTED" ? 2 : ["FUNDED", "DISPUTED", "CLOSED"].includes(a.status) ? 3 : 1;
  const n = open.length;
  const priced = price.data?.status === "PRICED";
  const monthlyOf = (o: any) => monthlyAnnuity(Number(o.amount), Number(o.rate), o.term_months);

  return (
    <div className="stack-l">
      <PageHeader title={a.status === "PUBLISHED" ? `${n} ${n === 1 ? "offer" : "offers"}` : chf(a.amount)} back="/sme/loans"
        subtitle={<><Pill tone={st.tone}>{st.label}</Pill><span className="num">{chf(a.amount)} · {Math.round(a.term_months / 12)} years{a.purpose ? ` · ${a.purpose}` : ""}</span></>} />
      <ErrorNote error={err} />

      {chosenDone && <Card><Success title="Offer chosen"><Button variant="secondary" onClick={() => setChosenDone(false)}>Continue</Button></Success></Card>}
      {!chosenDone && a.status === "FUNDED" && (
        <div className="banner"><div style={{ flex: 1 }}><b>Paid out {date(a.funded_at)}</b><div className="t-cap">{daysLeft(a.dispute_until)} days left to report a problem</div></div><Button size="sm" variant="danger-soft" onClick={() => setDispute(true)}>Report a problem</Button></div>
      )}
      {a.status === "DISPUTED" && <div className="banner">Problem reported.</div>}
      {a.status === "DRAFT" && <Button href={`/sme/loans/new?draft=${a.id}`}>Continue</Button>}

      {a.status === "PUBLISHED" && (
        <div className="stack">
          <div className="hstack wrap" style={{ gap: 32 }}>
            {assessment && <div className="stat"><span className="l">Rating</span><span className="v">{assessment.category}</span></div>}
            {range && <div className="stat"><span className="l">Fair rate</span><span className="v">{fmtRange(range)}</span></div>}
          </div>

          {n > 0 && !unlocked && (
            <div className="unlock-bar">
              <div className="hstack"><Icon name="lock" /><span>Lenders hidden</span></div>
              <Button onClick={checkout} disabled={!priced}>{priced ? `Unlock · ${chf(price.data.amount)}` : "Unlock"}</Button>
            </div>
          )}

          {offers.loading ? <Skeleton h={120} r={6} /> : n === 0 ? <Empty icon="clock" title="No offers yet" /> : (
            <div>
              <div className="offer-head"><span>Lender</span><span>Rate</span><span>Amount</span><span>Monthly</span><span /></div>
              <div className="offers">
                {open.map((o, i) => {
                  const tag = fairTag(Number(o.rate), range);
                  return (
                    <div key={o.id} className="offer enter" style={{ "--i": i } as any}>
                      <div className="who">
                        <span className={`avatar ${unlocked ? "" : "locked"}`}>{unlocked ? o.lender_name.charAt(0).toUpperCase() : ""}</span>
                        <div style={{ minWidth: 0 }}>
                          {i === 0 && n > 1 && <span className="best">Best</span>}
                          <div className="t-head">{unlocked ? o.lender_name : <span className="redact" aria-label="Hidden until unlocked" />}</div>
                          {tag && <div className={`fair ${tag.cls}`}>{tag.label}</div>}
                        </div>
                      </div>
                      <div><div className="k">Rate</div><div className="rate num">{Number(o.rate).toFixed(2)}%</div></div>
                      <div><div className="k">Amount</div><div className="v">{chf(o.amount, { compact: true })} · {Math.round(o.term_months / 12)}y</div></div>
                      <div><div className="k">Monthly</div><div className="v">≈ {chf(monthlyOf(o))}</div></div>
                      <div className="act"><Button size="sm" variant="secondary" onClick={() => { setErr(null); setDetail(o); }}>Details</Button></div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {live && <OfferSummary o={live} />}
      <div className="timeline">
        {stages.map((s, i) => <div className="item" key={s}><span className="dot" style={{ background: i <= stageIdx ? "var(--navy)" : "var(--bg)" }} /><span style={{ fontWeight: i === stageIdx ? 600 : 400, color: i <= stageIdx ? "var(--ink)" : "var(--ink-3)" }}>{s}</span></div>)}
      </div>
      {(a.status === "PUBLISHED" || a.status === "DRAFT") && <div><Button variant="plain" onClick={() => setWithdraw(true)}>Withdraw request</Button></div>}

      <Sheet open={!!detail} onClose={() => setDetail(null)} title={detail ? (unlocked ? detail.lender_name : "Offer") : ""}>
        {detail && <div className="stack">
          <dl className="kv"><dt>Rate</dt><dd>{ratePct(detail.rate)}</dd><dt>Amount</dt><dd>{chf(detail.amount)}</dd><dt>Term</dt><dd>{detail.term_months} months</dd>
            <dt>Repayment</dt><dd>{REPAYMENT[detail.repayment] ?? detail.repayment}</dd>{detail.collateral && <><dt>Security</dt><dd>{detail.collateral}</dd></>}
            <dt>Valid until</dt><dd>{date(detail.valid_until)}</dd></dl>
          <hr className="sep" />
          <dl className="kv total"><dt>Interest</dt><dd>{chf(detail.cost.interest)}</dd><dt>Lender fees</dt><dd>{chf(detail.cost.lender_fees)}</dd><dt><b>Total cost</b></dt><dd>{chf(detail.cost.total)}</dd></dl>
          <ErrorNote error={err} />
          {unlocked ? <Button block onClick={() => setPick(detail)}>Choose</Button> : <Button block onClick={() => { setDetail(null); checkout(); }} disabled={!priced}>Unlock to choose</Button>}
        </div>}
      </Sheet>
      <Sheet open={!!pick} onClose={() => setPick(null)} title="Choose this offer?">
        {pick && <div className="stack">
          <dl className="kv"><dt>Lender</dt><dd>{pick.lender_name}</dd><dt>Rate</dt><dd>{ratePct(pick.rate)}</dd><dt>Total cost</dt><dd>{chf(pick.cost.total)}</dd></dl>
          <ErrorNote error={err} />
          <Button block onClick={select}>Choose</Button><Button block variant="plain" onClick={() => setPick(null)}>Cancel</Button>
        </div>}
      </Sheet>
      <Sheet open={dispute} onClose={() => setDispute(false)} title="Report a problem?">
        <div className="stack"><ErrorNote error={err} /><Button block variant="danger" onClick={raise}>Report</Button><Button block variant="plain" onClick={() => setDispute(false)}>Cancel</Button></div>
      </Sheet>
      <Sheet open={withdraw} onClose={() => setWithdraw(false)} title="Withdraw request?">
        <div className="stack"><Button block variant="danger" onClick={withdrawApp}>Withdraw</Button><Button block variant="plain" onClick={() => setWithdraw(false)}>Cancel</Button></div>
      </Sheet>
    </div>
  );
}

function OfferSummary({ o }: { o: any }) {
  const st = OFFER_STATUS[o.status] ?? { label: o.status, tone: undefined };
  return (
    <div className="stack-s">
      <div className="hstack spread"><b className="t-head">{o.lender_name}</b><Pill tone={st.tone}>{st.label}</Pill></div>
      <dl className="kv"><dt>Rate</dt><dd>{ratePct(o.rate)}</dd><dt>Amount</dt><dd>{chf(o.amount)}</dd><dt>Total cost</dt><dd>{chf(o.cost?.total)}</dd></dl>
    </div>
  );
}

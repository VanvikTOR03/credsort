"use client";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api, invalidate, newKey, useApi } from "@/lib/client/api";
import { Button, Card, Empty, ErrorNote, PageHeader, Pill, Sheet, Skeleton, Success } from "@/components/ui";
import { Icon, Tile } from "@/components/Icon";
import { useToast } from "@/components/Providers";
import { APP_STATUS, OFFER_STATUS, REPAYMENT } from "@/lib/labels";
import { chf, date, daysLeft, ratePct } from "@/lib/format";
import { fairRange, fairTag, fmtRange, monthlyAnnuity } from "@/lib/loan";

const METHODS = [{ id: "TWINT", label: "TWINT", cls: "twint" }, { id: "VISA", label: "Visa", cls: "visa" }, { id: "MASTERCARD", label: "Mastercard", cls: "mc" }];

export default function LoanDetail() {
  const { id } = useParams<{ id: string }>(), router = useRouter(), toast = useToast();
  const app = useApi<any>("marketplace", `/v1/applications/${id}`, { refresh: 6000 });
  const offers = useApi<any[]>("marketplace", `/v1/applications/${id}/offers`, { refresh: 6000 });
  const assess = useApi<any[]>("intelligence", "/v1/assessments");
  const price = useApi<any>("billing", "/v1/unlock/price");
  const org = useApi<any>("identity", "/v1/organizations/current", { refresh: 8000 });
  const [pick, setPick] = useState<any>(null), [detail, setDetail] = useState<any>(null), [dispute, setDispute] = useState(false), [withdraw, setWithdraw] = useState(false);
  const [pay, setPay] = useState(false), [method, setMethod] = useState("TWINT"), [paid, setPaid] = useState(false), [paying, setPaying] = useState(false);
  const [err, setErr] = useState<any>(null), [chosenDone, setChosenDone] = useState(false);
  const a = app.data;
  const assessment = assess.data?.find((x) => x.id === a?.assessment_id) ?? assess.data?.[0];
  const range = fairRange(assessment?.category);
  const sorted = useMemo(() => [...(offers.data ?? [])].sort((x, y) => Number(x.cost?.total ?? 1e18) - Number(y.cost?.total ?? 1e18)), [offers.data]);
  const open = sorted.filter((o) => o.status === "SUBMITTED");
  const live = sorted.find((o) => ["SELECTED", "FUNDED", "DISPUTED"].includes(o.status));
  const unlocked = !!a?.unlocked_at || (offers.data?.[0]?.unlocked ?? false);

  useEffect(() => { // after payment the unlock event reaches the Marketplace within moments
    if (!paid || unlocked) return;
    const t = setInterval(() => invalidate("marketplace"), 1200);
    return () => clearInterval(t);
  }, [paid, unlocked]);

  async function payNow() {
    setErr(null); setPaying(true);
    try {
      await new Promise((r) => setTimeout(r, 900)); // the gateway round trip
      await api("billing", "/v1/unlock/payments", { method: "POST", body: { application_id: id, method } });
      setPaid(true); invalidate();
      setTimeout(() => { setPay(false); setPaid(false); toast("Offers unlocked"); }, 1800);
    } catch (e: any) { setErr(e); } finally { setPaying(false); }
  }
  async function select() {
    setErr(null);
    try { await api("marketplace", `/v1/offers/${pick.id}/selection`, { method: "POST", idem: newKey() }); invalidate(); setPick(null); setDetail(null); setChosenDone(true); window.scrollTo({ top: 0, behavior: "smooth" }); }
    catch (e: any) { setErr(e); }
  }
  async function raise() { setErr(null); try { await api("marketplace", `/v1/applications/${id}/dispute`, { method: "POST" }); invalidate(); setDispute(false); toast("We told your lender"); } catch (e: any) { setErr(e); } }
  async function withdrawApp() { setErr(null); try { await api("marketplace", `/v1/applications/${id}/withdraw`, { method: "POST" }); invalidate(); router.push("/sme/loans"); toast("Request withdrawn"); } catch (e: any) { setErr(e); } }

  if (app.loading) return <div className="stack-l"><PageHeader title="Loan" back="/sme/loans" /><Skeleton h={160} r={14} /></div>;
  if (!a) return <div className="stack-l"><PageHeader title="Loan" back="/sme/loans" /><ErrorNote error={app.error} retry={app.reload} /></div>;
  const st = APP_STATUS[a.status] ?? { label: a.status, tone: undefined };
  const stages = ["Requested", "Visible to lenders", "Offer chosen", "Funded"];
  const stageIdx = a.status === "DRAFT" ? 0 : a.status === "PUBLISHED" ? 1 : a.status === "OFFER_SELECTED" ? 2 : ["FUNDED", "DISPUTED", "CLOSED"].includes(a.status) ? 3 : 1;
  const n = open.length;
  const priced = price.data?.status === "PRICED";
  const monthlyOf = (o: any) => monthlyAnnuity(Number(o.amount), Number(o.rate), o.term_months);

  return (
    <div className="stack-l">
      <PageHeader title={a.status === "PUBLISHED" ? (n ? `${n} lender${n > 1 ? "s" : ""} sent you an offer${n > 1 ? "" : ""}` : "Waiting for offers") : chf(a.amount)} back="/sme/loans"
        subtitle={<span className="hstack wrap" style={{ gap: 8 }}><Pill tone={st.tone}>{st.label}</Pill><span>{chf(a.amount)} · {Math.round(a.term_months / 12)} years{a.purpose ? ` · ${a.purpose}` : ""}</span></span>}
        actions={undefined} />
      <ErrorNote error={err} />

      {a.status === "PUBLISHED" && (assessment || range) && (
        <div className="hstack wrap" style={{ gap: 10 }}>
          {assessment && <span className="card" style={{ padding: "8px 14px" }}><span className="t-foot">Estimated rating </span><b>{assessment.category}</b></span>}
          {range && <span className="card" style={{ padding: "8px 14px" }}><span className="t-foot">Fair rate range </span><b className="num">{fmtRange(range)}</b></span>}
        </div>
      )}

      {chosenDone && <Card><Success title="Offer chosen" text="We told your lender and shared your verified profile. Once they confirm the payout, the loan is complete."><Button variant="secondary" onClick={() => setChosenDone(false)}>Continue</Button></Success></Card>}
      {!chosenDone && a.status === "FUNDED" && (
        <div className="banner info enter"><Tile name="calendar" color="blue" size="sm" /><div className="grow"><b>Payout confirmed {date(a.funded_at)}</b><div className="t-cap">You have {daysLeft(a.dispute_until)} more days to raise a problem if the money did not arrive.</div></div><Button size="sm" variant="danger-soft" onClick={() => setDispute(true)}>Raise a problem</Button></div>
      )}
      {a.status === "DISPUTED" && <div className="banner enter"><Tile name="warning" color="orange" size="sm" /><div><b>Your problem was reported</b><div className="t-cap">We told the lender and are looking into it.</div></div></div>}
      {a.status === "DRAFT" && <Card className="stack"><p>This request is a draft. Lenders cannot see it yet.</p><Button href={`/sme/loans/new?draft=${a.id}`}>Continue</Button></Card>}

      {a.status === "PUBLISHED" && (
        <div className="unlock-grid">
          <div className="navy-panel">
            {unlocked ? (
              <>
                <Tile name="check" color="green" size="lg" />
                <h2 className="t-title">Offers unlocked</h2>
                <ul>
                  <li><Icon name="check" />Lender names and advisor contacts are visible</li>
                  <li><Icon name="check" />Choose one offer to start talks</li>
                  <li><Icon name="check" />Identity check: {org.data?.kyc_status === "VERIFIED" ? "verified by our partner" : org.data?.kyc_status === "REJECTED" ? "needs another look" : "in progress"}</li>
                </ul>
              </>
            ) : (
              <>
                <Tile name="lock" color="blue" size="lg" />
                <h2 className="t-title">Unlock lenders and start talks</h2>
                <ul>
                  <li><Icon name="check" />Identity and KYC check by our verified partner</li>
                  <li><Icon name="check" />Lender names and advisor contacts</li>
                  <li><Icon name="check" />Choose an offer and start talks in a few clicks</li>
                  <li><Icon name="check" />Your verified profile goes to the lender you pick</li>
                </ul>
                <div className="rule" />
                <div className="stack-s"><span className="muted">One-off fee per request</span><div className="num" style={{ fontSize: 40, fontWeight: 750, letterSpacing: "-.02em" }}>{priced ? chf(price.data.amount) : "To be confirmed"}</div></div>
                <Button block onClick={() => { setErr(null); setPay(true); }} disabled={!priced || n === 0}>{priced ? `View offers · ${chf(price.data.amount)}` : "Price not set yet"}</Button>
                <span className="t-foot">Covers the third-party identity check. Lenders pay CredSort only if a loan closes, and that fee is never added to your cost.</span>
              </>
            )}
          </div>

          <div className="stack">
            {offers.loading ? <Skeleton h={120} r={14} /> : n === 0 ? <Card><Empty icon="clock" color="blue" title="No offers yet" text="Matching lenders are reviewing your request. We will notify you as soon as one arrives." /></Card> : (
              open.map((o, i) => {
                const tag = fairTag(Number(o.rate), range);
                return (
                  <div key={o.id} className={`card offer-row enter ${i === 0 && n > 1 ? "best" : ""}`} style={{ "--i": i } as any}>
                    {i === 0 && n > 1 && <span className="badge-best">BEST OFFER</span>}
                    <div className="top">
                      <div className="hstack"><span className="avatar" style={unlocked ? undefined : { filter: "blur(3px)" }}>{unlocked ? o.lender_name.charAt(0).toUpperCase() : o.lender_name.slice(-1)}</span>
                        <div><div className={`t-head ${unlocked ? "" : "blur-name"}`}>{o.lender_name}</div><div className="t-foot">{unlocked ? "Lender" : "Name hidden until unlocked"}</div></div></div>
                      <div className="hstack" style={{ gap: 8, flexWrap: "wrap" }}>{tag && <span className={`fair ${tag.cls}`}>{tag.label}</span>}<Button size="sm" variant="secondary" onClick={() => { setErr(null); setDetail(o); }}>Details</Button></div>
                    </div>
                    <div className="stats">
                      <div><div className="k">Rate</div><div className="rate num" style={{ color: i === 0 && n > 1 ? "var(--green)" : undefined }}>{Number(o.rate).toFixed(2)}%</div></div>
                      <div><div className="k">Amount · term</div><div className="v">{chf(o.amount, { compact: true })} · {Math.round(o.term_months / 12)} yrs</div></div>
                      <div><div className="k">Monthly</div><div className="v">≈ {chf(monthlyOf(o))}</div></div>
                    </div>
                  </div>
                );
              })
            )}
            {n > 0 && <p className="t-foot">Illustrative monthly figures. Rates are compared with the fair range for similar firms. Sorted by total cost, lowest first.</p>}
          </div>
        </div>
      )}

      <Card className="enter">
        <div className="timeline">
          {stages.map((s, i) => <div className="item" key={s}><span className="dot" style={{ background: i <= stageIdx ? "var(--navy)" : "var(--surface)", borderColor: i <= stageIdx ? "var(--navy)" : "var(--sep)" }} /><div style={{ fontWeight: i === stageIdx ? 650 : 500, color: i <= stageIdx ? "var(--label)" : "var(--label-3)" }}>{s}</div></div>)}
        </div>
      </Card>
      {live && <OfferSummary o={live} />}
      {(a.status === "PUBLISHED" || a.status === "DRAFT") && <div className="center"><Button variant="plain" onClick={() => setWithdraw(true)}>Withdraw request</Button></div>}

      <Sheet open={!!detail} onClose={() => setDetail(null)} title={detail ? (unlocked ? detail.lender_name : "Offer details") : ""}>
        {detail && <div className="stack">
          <dl className="kv"><dt>Interest rate</dt><dd>{ratePct(detail.rate)} a year</dd><dt>Amount</dt><dd>{chf(detail.amount)}</dd><dt>Term</dt><dd>{detail.term_months} months</dd>
            <dt>Repayment</dt><dd>{REPAYMENT[detail.repayment] ?? detail.repayment}</dd>{detail.collateral && <><dt>Security</dt><dd>{detail.collateral}</dd></>}
            <dt>Valid until</dt><dd>{date(detail.valid_until)}</dd></dl>
          <hr className="sep" style={{ margin: 0 }} />
          <dl className="kv total"><dt>Interest over the term</dt><dd>{chf(detail.cost.interest)}</dd><dt>Lender fees</dt><dd>{chf(detail.cost.lender_fees)}</dd><dt><b>Total cost</b></dt><dd>{chf(detail.cost.total)}</dd></dl>
          <p className="t-foot">CredSort adds nothing to this: lenders pay CredSort only if the loan closes.</p>
          <ErrorNote error={err} />
          {unlocked ? <Button block onClick={() => { setPick(detail); }}>Choose this offer</Button> : <Button block onClick={() => { setDetail(null); setPay(true); }} disabled={!priced}>Unlock to choose {priced ? `· ${chf(price.data.amount)}` : ""}</Button>}
        </div>}
      </Sheet>
      <Sheet open={!!pick} onClose={() => setPick(null)} title="Choose this offer?">
        {pick && <div className="stack">
          <dl className="kv"><dt>Lender</dt><dd>{pick.lender_name}</dd><dt>Amount</dt><dd>{chf(pick.amount)}</dd><dt>Interest rate</dt><dd>{ratePct(pick.rate)} a year</dd><dt>Total cost</dt><dd>{chf(pick.cost.total)}</dd></dl>
          <p className="muted">Other offers are closed once you choose. Your verified profile goes to this lender.</p>
          <ErrorNote error={err} />
          <Button block onClick={select}>Yes, choose this offer</Button><Button block variant="plain" onClick={() => setPick(null)}>Not yet</Button>
        </div>}
      </Sheet>
      <Sheet open={pay} onClose={() => !paying && setPay(false)} title={paid ? "" : "Unlock offers"}>
        {paid ? <Success title="Payment successful" text="Demo payment: no money was charged. Your offers are being unlocked." /> : (
          <div className="stack">
            <div className="hstack spread"><span className="muted">One-off fee for this request</span><b className="num t-title">{priced ? chf(price.data.amount) : ""}</b></div>
            <div className="stack-s" role="radiogroup" aria-label="Payment method">
              {METHODS.map((m) => (
                <button key={m.id} className="pay-method" role="radio" aria-checked={method === m.id} onClick={() => setMethod(m.id)}><span className={`logo ${m.cls}`}>{m.label.toUpperCase()}</span>{m.label}</button>
              ))}
            </div>
            <p className="t-foot">This is a demonstration checkout. No card details are asked for and no money is charged.</p>
            <ErrorNote error={err} />
            <Button block onClick={payNow} loading={paying}>Pay {priced ? chf(price.data.amount) : ""}</Button>
          </div>
        )}
      </Sheet>
      <Sheet open={dispute} onClose={() => setDispute(false)} title="Did the money not arrive?">
        <div className="stack"><p>We will tell your lender and look into it. Only continue if you did not receive the loan amount.</p><ErrorNote error={err} /><Button block variant="danger" onClick={raise}>Report a problem</Button><Button block variant="plain" onClick={() => setDispute(false)}>Cancel</Button></div>
      </Sheet>
      <Sheet open={withdraw} onClose={() => setWithdraw(false)} title="Withdraw this request?">
        <div className="stack"><p>Lenders will no longer see it and open offers are closed. The unlock fee, if you paid it, is not refunded.</p><Button block variant="danger" onClick={withdrawApp}>Withdraw</Button><Button block variant="plain" onClick={() => setWithdraw(false)}>Keep it</Button></div>
      </Sheet>
    </div>
  );
}

function OfferSummary({ o }: { o: any }) {
  const st = OFFER_STATUS[o.status] ?? { label: o.status, tone: undefined };
  return (
    <Card className="stack">
      <div className="hstack spread"><div className="hstack"><Tile name="bank" color="indigo" size="sm" /><b className="t-head">{o.lender_name}</b></div><Pill tone={st.tone}>{st.label}</Pill></div>
      <dl className="kv"><dt>Rate</dt><dd>{ratePct(o.rate)} a year</dd><dt>Amount</dt><dd>{chf(o.amount)}</dd><dt>Term</dt><dd>{o.term_months} months</dd><dt>Total cost</dt><dd>{chf(o.cost?.total)}</dd></dl>
    </Card>
  );
}

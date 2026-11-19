"use client";
import { useState } from "react";
import { api, invalidate, useApi } from "@/lib/client/api";
import { Button, Card, Empty, ErrorNote, ListSkeleton, PageHeader, Pill, Section, Sheet } from "@/components/ui";
import { Tile } from "@/components/Icon";
import { useToast } from "@/components/Providers";
import { OFFER_STATUS } from "@/lib/labels";
import { chf, date, ratePct } from "@/lib/format";

export default function LenderOffers() {
  const toast = useToast();
  const offers = useApi<any[]>("marketplace", "/v1/lender/offers", { refresh: 10000 });
  const [act, setAct] = useState<{ kind: "payout" | "cancel" | "withdraw"; o: any } | null>(null), [err, setErr] = useState<any>(null);
  async function run() {
    if (!act) return; setErr(null);
    const path = { payout: "confirm-payout", cancel: "cancel-loan", withdraw: "withdraw" }[act.kind];
    try { await api("marketplace", `/v1/lender/offers/${act.o.id}/${path}`, { method: "POST" }); invalidate(); setAct(null); toast({ payout: "Payout confirmed", cancel: "Loan cancelled", withdraw: "Offer withdrawn" }[act.kind]); } catch (e: any) { setErr(e); }
  }
  const groups = [
    { title: "Waiting for you", items: (offers.data ?? []).filter((o) => o.status === "SELECTED") },
    { title: "Open offers", items: (offers.data ?? []).filter((o) => o.status === "SUBMITTED") },
    { title: "Completed", items: (offers.data ?? []).filter((o) => !["SELECTED", "SUBMITTED"].includes(o.status)) },
  ].filter((g) => g.items.length);
  return (
    <div className="stack-l">
      <PageHeader title="Offers" subtitle="Everything you have offered, and what needs you." />
      {offers.loading ? <ListSkeleton rows={2} /> : !groups.length ? <Card><Empty icon="loan" color="orange" title="No offers yet" text="Open a match and make an offer. It takes about a minute." action={<Button href="/lender">See matches</Button>} /></Card> : groups.map((g) => (
        <Section key={g.title} title={g.title}>
          <div className="stack">{g.items.map((o) => { const st = OFFER_STATUS[o.status] ?? { label: o.status, tone: undefined };
            return (
              <Card key={o.id} className="stack enter">
                <div className="hstack spread"><div><div className="t-head num">{chf(o.amount)}</div><div className="t-foot">{ratePct(o.rate)} · {o.term_months} months · valid until {date(o.valid_until)}</div></div><Pill tone={st.tone}>{st.label}</Pill></div>
                {o.status === "SELECTED" && <><div className="banner info"><Tile name="check" color="accent" size="sm" /><div>The company chose your offer. Once you have paid out, confirm it here. They then have 14 days to raise a problem.</div></div><div className="hstack"><div className="grow"><Button block variant="secondary" onClick={() => setAct({ kind: "cancel", o })}>Cancel loan</Button></div><div className="grow"><Button block onClick={() => setAct({ kind: "payout", o })}>Confirm payout</Button></div></div></>}
                {o.status === "SUBMITTED" && <Button variant="secondary" onClick={() => setAct({ kind: "withdraw", o })}>Withdraw offer</Button>}
              </Card>); })}</div>
        </Section>
      ))}
      <Sheet open={!!act} onClose={() => setAct(null)} title={act?.kind === "payout" ? "Confirm the payout?" : act?.kind === "cancel" ? "Cancel this loan?" : "Withdraw this offer?"}>
        {act && <div className="stack">
          <p>{act.kind === "payout" ? `Only confirm after ${chf(act.o.amount)} has actually been paid to the company. CredSort never handles loan money.` : act.kind === "cancel" ? "The company is told, and no fee is due for this loan." : "The company will no longer see this offer."}</p>
          <ErrorNote error={err} />
          <Button block variant={act.kind === "payout" ? undefined : "danger"} onClick={run}>{act.kind === "payout" ? "Yes, money was paid out" : act.kind === "cancel" ? "Cancel loan" : "Withdraw"}</Button>
          <Button block variant="plain" onClick={() => setAct(null)}>Back</Button>
        </div>}
      </Sheet>
    </div>
  );
}

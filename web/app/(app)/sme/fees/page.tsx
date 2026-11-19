"use client";
import { useApi } from "@/lib/client/api";
import { Card, List, ListSkeleton, PageHeader, Pill, Row, Section } from "@/components/ui";
import { Tile } from "@/components/Icon";
import { CHARGE_STATUS } from "@/lib/labels";
import { chf, date } from "@/lib/format";

export default function Fees() {
  const pricing = useApi<any>("billing", "/v1/pricing");
  const charges = useApi<any[]>("billing", "/v1/charges");
  const rule = pricing.data?.rules?.find((r: any) => r.payer === "SME");
  return (
    <div className="stack-l">
      <PageHeader title="Fees" back="/sme/more" subtitle="Simple: you pay only when a loan is funded." />
      <Card className="stack enter">
        <div className="hstack"><Tile name="receipt" color="green" /><div><div className="t-head">Success fee only</div><div className="t-foot">No sign-up fee. No subscription. Every feature included.</div></div></div>
        {pricing.loading ? <ListSkeleton rows={1} /> : pricing.data?.status === "ACTIVE" && rule ? (
          <div className="stack-s">
            <p>When a lender confirms your payout, CredSort charges <b>{Number(rule.percent)}%</b> of the loan, at least {chf(rule.min_amount)} and at most {chf(rule.cap_amount)}.</p>
            {pricing.data.placeholder && <Pill tone="orange">Demo prices, not final</Pill>}
          </div>
        ) : <p className="muted">The price is not set yet. We will always show it next to every offer, before you choose.</p>}
        <ul className="stack-s" style={{ margin: 0, paddingLeft: 20 }}>
          <li>The price is locked when you choose an offer.</li>
          <li>You have 14 days after the payout to raise a problem. The fee waits until then.</li>
          <li>If the loan is cancelled, nothing is due.</li>
        </ul>
      </Card>
      <Section title="Your charges">
        {charges.loading ? <ListSkeleton rows={1} /> : charges.data?.length ? (
          <List>{charges.data.map((c) => { const s = CHARGE_STATUS[c.status] ?? { label: c.status, tone: undefined, help: "" };
            return <Row key={c.id} icon="receipt" color="gray" title={<span className="num">{chf(c.amount)}</span>} sub={`${s.help}${c.status === "PENDING" ? ` Payable after ${date(c.payable_after)}.` : ""}`} value={<Pill tone={s.tone}>{s.label}</Pill>} />; })}</List>
        ) : <Card><p className="muted center">No charges. You have not had a loan funded yet.</p></Card>}
      </Section>
    </div>
  );
}

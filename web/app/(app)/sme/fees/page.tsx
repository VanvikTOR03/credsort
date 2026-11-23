"use client";
import { useApi } from "@/lib/client/api";
import { Card, List, ListSkeleton, PageHeader, Pill, Row, Section } from "@/components/ui";
import { Tile } from "@/components/Icon";
import { chf, date } from "@/lib/format";

export default function Fees() {
  const price = useApi<any>("billing", "/v1/unlock/price");
  const pays = useApi<any[]>("billing", "/v1/unlock/payments");
  return (
    <div className="stack-l">
      <PageHeader title="Fees" back="/sme/more" subtitle="One simple fee per loan request." />
      <Card className="stack enter">
        <div className="hstack"><Tile name="receipt" color="blue" /><div><div className="t-head">One-off unlock fee</div><div className="t-foot">Paid once per loan request, only when you want to see who made the offers.</div></div></div>
        {price.loading ? <ListSkeleton rows={1} /> : price.data?.status === "PRICED" ? (
          <div className="hstack spread"><span className="num t-large">{chf(price.data.amount)}</span>{price.data.placeholder && <Pill tone="orange">Demo price, not final</Pill>}</div>
        ) : <p className="muted">The price is not set yet.</p>}
        <ul className="stack-s" style={{ margin: 0, paddingLeft: 20 }}>
          <li>It covers the identity check done by our verification partner.</li>
          <li>You can compare offers and see the fair rate range before paying.</li>
          <li>There is no success fee for you. Lenders pay CredSort a share only if a loan closes, and it is never added to your cost.</li>
          <li>The fee is not refunded if no offer suits you.</li>
        </ul>
        <p className="t-foot">Pay with TWINT, Visa or Mastercard.</p>
      </Card>
      <Section title="Your payments">
        {pays.loading ? <ListSkeleton rows={1} /> : pays.data?.length ? (
          <List>{pays.data.map((p) => <Row key={p.id} icon="receipt" color="gray" title={<span className="num">{chf(p.amount, { decimals: 2 })}</span>} sub={`${p.method === "MASTERCARD" ? "Mastercard" : p.method === "VISA" ? "Visa" : "TWINT"} · ${date(p.created_at)} · ${p.provider === "demo" ? "demo payment" : p.provider_ref}`} value={<Pill tone="green">Paid</Pill>} href={`/sme/loans/${p.application_id}`} />)}</List>
        ) : <Card><p className="muted center">No payments yet.</p></Card>}
      </Section>
    </div>
  );
}

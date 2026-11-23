"use client";
import { useApi } from "@/lib/client/api";
import { Card, List, ListSkeleton, PageHeader, Pill, Row, Section } from "@/components/ui";
import { chf, date } from "@/lib/format";

const METHOD: Record<string, string> = { MASTERCARD: "Mastercard", VISA: "Visa", TWINT: "TWINT" };

export default function Fees() {
  const price = useApi<any>("billing", "/v1/unlock/price");
  const pays = useApi<any[]>("billing", "/v1/unlock/payments");
  return (
    <div className="stack-l">
      <PageHeader title="Fees" back="/sme/more" />
      <Card className="kpi"><span className="l">Per loan request, once</span>
        <span className="v">{price.data?.status === "PRICED" ? chf(price.data.amount) : "n/a"}</span>
        {price.data?.placeholder && <span className="c">Demo price</span>}</Card>
      <Section title="Payments">
        {pays.loading ? <ListSkeleton rows={1} /> : pays.data?.length ? (
          <List>{pays.data.map((p) => <Row key={p.id} icon="receipt" href={`/sme/loans/${p.application_id}`} title={<span className="num">{chf(p.amount, { decimals: 2 })}</span>} sub={`${METHOD[p.method] ?? p.method} · ${date(p.created_at)}`} value={<Pill tone="green">Paid</Pill>} />)}</List>
        ) : <p className="muted" style={{ padding: "20px 0" }}>None</p>}
      </Section>
    </div>
  );
}

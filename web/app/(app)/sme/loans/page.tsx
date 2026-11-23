"use client";
import { useApi } from "@/lib/client/api";
import { Button, Empty, List, ListSkeleton, PageHeader, Pill, Row, Card } from "@/components/ui";
import { APP_STATUS } from "@/lib/labels";
import { chf, ago } from "@/lib/format";

export default function Loans() {
  const apps = useApi<any[]>("marketplace", "/v1/applications");
  const list = (apps.data ?? []).filter((a) => a.status !== "WITHDRAWN");
  return (
    <div className="stack-l">
      <PageHeader title="Loans" actions={list.length ? <Button size="sm" href="/sme/loans/new" icon="plus">New</Button> : undefined} />
      {apps.loading ? <ListSkeleton rows={2} /> : list.length === 0 ? (
        <Card><Empty icon="loan" color="orange" title="No loan request yet" action={<Button href="/sme/loans/new">Start a request</Button>} /></Card>
      ) : (
        <List>{list.map((a) => {
          const st = APP_STATUS[a.status] ?? { label: a.status, tone: undefined };
          return <Row key={a.id} icon="loan" tone={a.status === "FUNDED" ? "ok" : undefined} href={`/sme/loans/${a.id}`} title={<span className="num">{chf(a.amount)}</span>}
            sub={`${a.term_months} months${a.purpose ? ` · ${a.purpose}` : ""} · ${ago(a.created_at)}`} value={<span className="hstack" style={{ gap: 8 }}>{a.status === "PUBLISHED" && a.open_offers > 0 && <Pill tone="accent">{a.open_offers} offer{a.open_offers > 1 ? "s" : ""}</Pill>}<Pill tone={st.tone}>{st.label}</Pill></span>} />;
        })}</List>
      )}
    </div>
  );
}

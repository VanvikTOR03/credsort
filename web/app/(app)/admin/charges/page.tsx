"use client";
import { api, invalidate, useApi } from "@/lib/client/api";
import { Button, Card, Empty, ListSkeleton, PageHeader, Pill, Row, List } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { CHARGE_STATUS } from "@/lib/labels";
import { chf, date } from "@/lib/format";

export default function Charges() {
  const toast = useToast();
  const c = useApi<any[]>("billing", "/v1/admin/charges", { refresh: 10000 });
  const run = async (id: string, what: "release" | "waive") => { try { await api("billing", `/v1/admin/charges/${id}/${what}`, { method: "POST" }); invalidate(); toast(what === "release" ? "Charge released" : "Charge waived"); } catch (e: any) { toast(e.detail, "error"); } };
  return (
    <div className="stack-l">
      <PageHeader title="Charges" subtitle="Exactly what was quoted, one per funded loan." />
      {c.loading ? <ListSkeleton rows={3} /> : !c.data?.length ? <Card><Empty icon="receipt" color="green" title="No charges yet" text="Charges appear when a lender confirms a payout." /></Card> : (
        <List>{c.data.map((x) => { const s = CHARGE_STATUS[x.status] ?? { label: x.status, tone: undefined, help: "" };
          return <Row key={x.id} icon="receipt" color="gray" title={<span className="num">{chf(x.amount)}</span>} sub={`Loan ${chf(x.basis)} · payable after ${date(x.payable_after)}`} value={<Pill tone={s.tone}>{s.label}</Pill>}>
            {["HELD", "PENDING"].includes(x.status) && <span className="hstack" style={{ gap: 6 }}><Button size="sm" variant="secondary" onClick={() => run(x.id, "waive")}>Waive</Button>{x.status === "HELD" && <Button size="sm" onClick={() => run(x.id, "release")}>Release</Button>}</span>}
          </Row>; })}</List>
      )}
    </div>
  );
}

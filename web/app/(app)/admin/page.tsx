"use client";
import { api, invalidate, useApi } from "@/lib/client/api";
import { Button, Card, Empty, List, ListSkeleton, PageHeader, Pill, Row, Section } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { Tile } from "@/components/Icon";
import { ago } from "@/lib/format";

const ICON: Record<string, [string, string]> = { SME: ["building", "blue"], LENDER: ["bank", "indigo"], FIDUCIARY: ["people", "green"], PLATFORM: ["shield", "gray"] };
export default function Review() {
  const toast = useToast();
  const orgs = useApi<any[]>("identity", "/v1/admin/organizations");
  const act = async (id: string, what: string, msg: string) => { try { await api("identity", `/v1/admin/organizations/${id}/${what}`, { method: "POST" }); invalidate(); toast(msg); } catch (e: any) { toast(e.detail, "error"); } };
  const pending = (orgs.data ?? []).filter((o) => o.kyb_status === "PENDING");
  const rest = (orgs.data ?? []).filter((o) => o.kyb_status !== "PENDING" && o.type !== "PLATFORM");
  return (
    <div className="stack-l">
      <PageHeader title="Review" />
      <Section title={`Waiting (${pending.length})`}>
        {orgs.loading ? <ListSkeleton rows={2} /> : pending.length ? (
          <div className="stack">{pending.map((o) => { const [i, c] = ICON[o.type] ?? ICON.SME; return (
            <Card key={o.id} className="stack enter"><div className="hstack"><Tile name={i} color={c} /><div className="grow"><b className="t-head">{o.legal_name}</b><div className="t-foot">{o.type.toLowerCase()} · {o.uid ?? "no UID"} · {ago(o.created_at)}</div></div></div>
              <div className="hstack"><div className="grow"><Button block variant="danger-soft" onClick={() => act(o.id, "reject", "Rejected")}>Reject</Button></div><div className="grow"><Button block onClick={() => act(o.id, "verify", "Verified")}>Verify</Button></div></div></Card>); })}</div>
        ) : <Card><Empty icon="check" color="green" title="All caught up" /></Card>}
      </Section>
      <Section title="Everyone else">
        <List>{rest.map((o) => { const [i, c] = ICON[o.type] ?? ICON.SME; return (
          <Row key={o.id} icon={i} color={c} title={o.legal_name} sub={`${o.type.toLowerCase()} · ${o.status.toLowerCase()}`} value={<Pill tone={o.kyb_status === "VERIFIED" ? "green" : "red"}>{o.kyb_status.toLowerCase()}</Pill>}>
            {o.status === "ACTIVE" && <Button size="sm" variant="danger-soft" onClick={() => act(o.id, "suspend", "Suspended")}>Suspend</Button>}
          </Row>); })}</List>
      </Section>
    </div>
  );
}

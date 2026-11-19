"use client";
import { useState } from "react";
import { api, invalidate, useApi } from "@/lib/client/api";
import { Button, Card, Empty, ErrorNote, List, ListSkeleton, PageHeader, Pill, Row, Section, Sheet } from "@/components/ui";
import { Tile } from "@/components/Icon";
import { useToast } from "@/components/Providers";
import { FIELD_PLAIN } from "@/lib/labels";
import { ago } from "@/lib/format";

const label = (f: string) => FIELD_PLAIN[f]?.replace(/^(How|What|Your|A|Roughly|Share of|Can you|Cash|Years of|Operating|Final|Total)\s?/i, (m) => m) ?? f.replace(/_/g, " ");

export default function Privacy() {
  const toast = useToast();
  const disclosures = useApi<any[]>("marketplace", "/v1/disclosures");
  const requests = useApi<any[]>("marketplace", "/v1/access-requests", { refresh: 10000 });
  const activity = useApi<any[]>("audit", "/v1/activity");
  const [confirmAll, setConfirmAll] = useState(false), [err, setErr] = useState<any>(null);
  const pending = (requests.data ?? []).filter((r) => r.status === "PENDING");

  async function decide(id: string, ok: boolean) {
    try { await api("marketplace", `/v1/access-requests/${id}/${ok ? "approve" : "deny"}`, { method: "POST" }); invalidate(); toast(ok ? "Access granted" : "Request declined"); } catch (e: any) { toast(e.detail, "error"); }
  }
  async function revoke(id: string) { try { await api("marketplace", `/v1/disclosures/${id}/revoke`, { method: "POST" }); invalidate(); toast("Sharing stopped"); } catch (e: any) { toast(e.detail, "error"); } }
  async function revokeAll() { setErr(null); try { await api("marketplace", "/v1/disclosures/revoke-all", { method: "POST" }); invalidate(); setConfirmAll(false); toast("You stopped sharing with everyone"); } catch (e: any) { setErr(e); } }

  return (
    <div className="stack-l">
      <PageHeader title="Privacy" subtitle="You decide who sees what. Changes take effect immediately." />
      {pending.length > 0 && (
        <Section title="Waiting for you">
          <div className="stack">{pending.map((r) => (
            <Card key={r.id} className="stack enter">
              <div className="hstack"><Tile name="eye" color="orange" size="sm" /><b>A lender asks for more detail</b></div>
              <div className="stack-s">{r.requested_fields.map((f: string) => <div key={f} className="hstack" style={{ gap: 8 }}><Tile name="check" color="gray" size="xs" /><span>{label(f)}</span></div>)}</div>
              <div className="hstack"><div className="grow"><Button block variant="secondary" onClick={() => decide(r.id, false)}>Decline</Button></div><div className="grow"><Button block onClick={() => decide(r.id, true)}>Allow</Button></div></div>
            </Card>))}</div>
        </Section>
      )}
      <Section title="Currently shared" footer="Lenders only ever see the fields you ticked, as they were when you published.">
        {disclosures.loading ? <ListSkeleton rows={2} /> : disclosures.data?.length ? (
          <List>{disclosures.data.map((d) => (
            <Row key={d.id} icon="eye" color="indigo" title={d.lender_org_id ? "One lender, extra detail" : "Matching lenders"} sub={`${d.permitted_fields.length} details · since ${ago(d.granted_at)}`}>
              <Button size="sm" variant="danger-soft" onClick={() => revoke(d.id)}>Stop</Button>
            </Row>))}</List>
        ) : <Card><Empty icon="lock" color="green" title="Nothing is shared" text="Lenders see nothing about you until you publish a loan request." /></Card>}
      </Section>
      {!!disclosures.data?.length && <Button block variant="danger-soft" onClick={() => setConfirmAll(true)}>Stop sharing with everyone</Button>}
      <Section title="Activity" footer="A tamper-evident record of what happened to your data.">
        {activity.loading ? <ListSkeleton rows={3} /> : activity.data?.length ? (
          <List>{activity.data.slice(0, 12).map((a) => <Row key={a.id} icon="clock" color="gray" title={a.label} sub={`${a.by === "you" ? "You" : a.by === "platform" ? "CredSort" : "Someone else"} · ${ago(a.occurred_at)}`} />)}</List>
        ) : <Card><p className="muted center">No activity yet.</p></Card>}
      </Section>
      <Sheet open={confirmAll} onClose={() => setConfirmAll(false)} title="Stop sharing with everyone?">
        <div className="stack"><p>Every lender loses access right away. Your requests stay saved and you can publish again later.</p><ErrorNote error={err} /><Button block variant="danger" onClick={revokeAll}>Stop sharing</Button><Button block variant="plain" onClick={() => setConfirmAll(false)}>Cancel</Button></div>
      </Sheet>
    </div>
  );
}

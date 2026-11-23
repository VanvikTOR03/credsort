"use client";
import { useState } from "react";
import { api, invalidate, useApi } from "@/lib/client/api";
import { Button, Card, Empty, ErrorNote, List, ListSkeleton, PageHeader, Row, Section, Sheet } from "@/components/ui";
import { Tile } from "@/components/Icon";
import { useToast } from "@/components/Providers";
import { ago } from "@/lib/format";

export default function Privacy() {
  const toast = useToast();
  const disclosures = useApi<any[]>("marketplace", "/v1/disclosures");
  const activity = useApi<any[]>("audit", "/v1/activity");
  const [confirmAll, setConfirmAll] = useState(false), [err, setErr] = useState<any>(null);
  async function revoke(id: string) { try { await api("marketplace", `/v1/disclosures/${id}/revoke`, { method: "POST" }); invalidate(); toast("Sharing stopped"); } catch (e: any) { toast(e.detail, "error"); } }
  async function revokeAll() { setErr(null); try { await api("marketplace", "/v1/disclosures/revoke-all", { method: "POST" }); invalidate(); setConfirmAll(false); toast("You stopped sharing with everyone"); } catch (e: any) { setErr(e); } }
  return (
    <div className="stack-l">
      <PageHeader title="Privacy" />
      <Section title="Currently shared">
        {disclosures.loading ? <ListSkeleton rows={2} /> : disclosures.data?.length ? (
          <List>{disclosures.data.map((d) => (
            <Row key={d.id} icon="eye" color="indigo" title="Matching lenders" sub={`Since ${ago(d.granted_at)}`}><Button size="sm" variant="danger-soft" onClick={() => revoke(d.id)}>Stop</Button></Row>))}</List>
        ) : <Card><p className="muted" style={{ padding: "20px 0" }}>Nothing is shared</p></Card>}
      </Section>
      {!!disclosures.data?.length && <Button block variant="danger-soft" onClick={() => setConfirmAll(true)}>Stop sharing with everyone</Button>}
      <Section title="Activity">
        {activity.loading ? <ListSkeleton rows={3} /> : activity.data?.length ? (
          <List>{activity.data.slice(0, 12).map((a) => <Row key={a.id} icon="clock" color="gray" title={a.label} sub={`${a.by === "you" ? "You" : a.by === "platform" ? "CredSort" : "Someone else"} · ${ago(a.occurred_at)}`} />)}</List>
        ) : <Card><p className="muted center">No activity yet.</p></Card>}
      </Section>
      <Sheet open={confirmAll} onClose={() => setConfirmAll(false)} title="Stop sharing with everyone?">
        <div className="stack"><p>Every lender loses access right away. Your requests stay saved and you can request offers again later.</p><ErrorNote error={err} /><Button block variant="danger" onClick={revokeAll}>Stop sharing</Button><Button block variant="plain" onClick={() => setConfirmAll(false)}>Cancel</Button></div>
      </Sheet>
    </div>
  );
}

"use client";
import { useState } from "react";
import { api, invalidate, useApi } from "@/lib/client/api";
import { Button, Card, Empty, ErrorNote, Field, List, ListSkeleton, PageHeader, Row, Section, Pill } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { ago } from "@/lib/format";

export default function Accountant() {
  const toast = useToast();
  const d = useApi<any[]>("identity", "/v1/delegations");
  const [code, setCode] = useState(""), [err, setErr] = useState<any>(null);
  async function grant() {
    setErr(null);
    try { await api("identity", "/v1/delegations", { method: "POST", body: { referral_code: code.trim(), scopes: ["VIEW_PROFILE", "PREPARE_APPLICATION"] } }); invalidate("identity"); setCode(""); toast("Your accountant now has access"); } catch (e: any) { setErr(e); }
  }
  return (
    <div className="stack-l">
      <PageHeader title="Accountant" back="/sme/more" />
      <Section title="Who has access">
        {d.loading ? <ListSkeleton rows={1} /> : d.data?.filter((x) => !x.revoked_at).length ? (
          <List>{d.data.filter((x) => !x.revoked_at).map((x) => <Row key={x.id} icon="people" color="green" title={x.fiduciary_name} sub={`Since ${ago(x.granted_at)}`}><Button size="sm" variant="danger-soft" onClick={async () => { await api("identity", `/v1/delegations/${x.id}`, { method: "DELETE" }); invalidate("identity"); toast("Access removed"); }}>Remove</Button></Row>)}</List>
        ) : <Card><Empty icon="people" color="green" title="No one yet" /></Card>}
      </Section>
      <Section title="Add your accountant">
        <List><Field label="Referral code"><input value={code} onChange={(e) => setCode(e.target.value)} placeholder="CS-XXXXXX" autoCapitalize="characters" /></Field></List>
        <div style={{ marginTop: 12 }}><ErrorNote error={err} /></div>
        <div style={{ marginTop: 12 }}><Button block onClick={grant} disabled={code.trim().length < 4}>Give access</Button></div>
      </Section>
    </div>
  );
}

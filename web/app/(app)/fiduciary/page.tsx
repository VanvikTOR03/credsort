"use client";
import { useRouter } from "next/navigation";
import { api, invalidate, useApi } from "@/lib/client/api";
import { Button, Card, Empty, List, ListSkeleton, PageHeader, Pill, Row, Section } from "@/components/ui";
import { Tile } from "@/components/Icon";
import { useSession, useToast } from "@/components/Providers";

export default function Clients() {
  const { session, reload } = useSession(), router = useRouter(), toast = useToast();
  const clients = useApi<any[]>("identity", "/v1/fiduciary/clients");
  const org = useApi<any>("identity", "/v1/organizations/current");
  async function work(c: any) {
    const r = await fetch("/api/session/act-for", { method: "POST", headers: { "content-type": "application/json", "x-csrf": session!.csrf }, body: JSON.stringify({ sme_org_id: c.sme_org_id, sme_name: c.sme_name }) });
    if (!r.ok) { toast((await r.json()).detail ?? "Could not start", "error"); return; }
    invalidate(); await reload(); router.push("/sme");
  }
  return (
    <div className="stack-l">
      <PageHeader title="Clients" />
      <div className="two-col">
      {clients.loading ? <ListSkeleton rows={2} /> : !clients.data?.length ? <Card><Empty icon="people" color="green" title="No clients yet" /></Card> : (
        <List>{clients.data.map((c) => <Row key={c.id} icon="building" color="orange" title={c.sme_name} sub={c.scopes.includes("PREPARE_APPLICATION") ? "Can view and prepare applications" : "Can view the profile"}><Button size="sm" onClick={() => work(c)}>Open</Button></Row>)}</List>
      )}
      {org.data?.referral_code && <Section title="Your referral code"><Card className="hstack spread"><b className="num t-title" style={{ letterSpacing: ".04em" }}>{org.data.referral_code}</b><Button size="sm" variant="secondary" onClick={() => { navigator.clipboard?.writeText(org.data.referral_code); toast("Code copied"); }}>Copy</Button></Card></Section>}
      </div>
    </div>
  );
}

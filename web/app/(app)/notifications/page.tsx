"use client";
import { useRouter } from "next/navigation";
import { api, invalidate, useApi } from "@/lib/client/api";
import { Button, Card, Empty, List, ListSkeleton, PageHeader, Row } from "@/components/ui";
import { ago } from "@/lib/format";

const ICON: Record<string, [string, string]> = { "loan.funded": ["loan", "green"], "offer.submitted": ["loan", "orange"], "offer.selected": ["check", "accent"], "charge.changed": ["receipt", "gray"], "access.requested": ["eye", "indigo"], "assessment.created": ["gauge", "blue"] };
export default function Notifications() {
  const router = useRouter();
  const n = useApi<{ unread: number; items: any[] }>("notification", "/v1/notifications", { refresh: 15000 });
  async function open(x: any) { if (!x.read_at) { await api("notification", `/v1/notifications/${x.id}/read`, { method: "POST" }).catch(() => {}); invalidate("notification"); } if (x.link) router.push(x.link); }
  return (
    <div className="stack-l">
      <PageHeader title="Notifications" subtitle={n.data?.unread ? `${n.data.unread} new` : "You are all caught up."} actions={n.data?.unread ? <Button size="sm" variant="plain" onClick={async () => { await api("notification", "/v1/notifications/read-all", { method: "POST" }); invalidate("notification"); }}>Mark all read</Button> : undefined} />
      {n.loading ? <ListSkeleton rows={4} /> : !n.data?.items.length ? <Card><Empty icon="bell" color="red" title="Nothing yet" text="We will tell you when something needs your attention." /></Card> : (
        <List>{n.data.items.map((x) => { const [icon, color] = ICON[x.kind] ?? ["bell", "red"];
          return <Row key={x.id} icon={icon} color={color} onClick={() => open(x)} title={<span style={{ fontWeight: x.read_at ? 500 : 700 }}>{x.title}</span>} sub={`${x.body} · ${ago(x.created_at)}`} value={!x.read_at ? <span className="tile xs c-blue" style={{ width: 10, height: 10 }} /> : undefined} />; })}</List>
      )}
    </div>
  );
}

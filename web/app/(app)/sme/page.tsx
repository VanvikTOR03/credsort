"use client";
import { useMemo } from "react";
import { useApi } from "@/lib/client/api";
import { useSession } from "@/components/Providers";
import { Button, Card, List, PageHeader, Row, Section, Skeleton } from "@/components/ui";
import { RangeBar } from "@/components/RangeBar";
import { Tile } from "@/components/Icon";
import { CATEGORY } from "@/lib/labels";
import { daysLeft } from "@/lib/format";
import { fairRange, fmtRange } from "@/lib/loan";

export default function SmeHome() {
  const { session } = useSession();
  const s = session!;
  const assess = useApi<any[]>("intelligence", "/v1/assessments");
  const conns = useApi<any[]>("accounting", "/v1/connections");
  const apps = useApi<any[]>("marketplace", "/v1/applications");
  const latest = assess.data?.[0];
  const range = fairRange(latest?.category);
  const loading = assess.loading || conns.loading || apps.loading;

  const next = useMemo(() => {
    // the request that needs attention first: a payout window, a chosen offer, offers to compare, then the rest
    const rank = (x: any) => (x.status === "FUNDED" && daysLeft(x.dispute_until) > 0 ? 0 : x.status === "OFFER_SELECTED" ? 1 : x.status === "PUBLISHED" && x.open_offers > 0 ? 2 : x.status === "PUBLISHED" ? 3 : x.status === "DRAFT" ? 4 : 9);
    const active = [...(apps.data ?? [])].sort((p, q) => rank(p) - rank(q)).find((x) => rank(x) < 9);
    if (!conns.data?.length) return { icon: "plug", title: "Add your accounts", cta: "Add accounts", href: "/sme/finances?tab=data" };
    if (!latest) return { icon: "gauge", title: "Calculating your rating", cta: "View", href: "/sme/finances?tab=data" };
    if (active?.status === "FUNDED" && active.dispute_until && daysLeft(active.dispute_until) > 0) return { icon: "calendar", title: `Paid out · ${daysLeft(active.dispute_until)} days to report a problem`, cta: "View loan", href: `/sme/loans/${active.id}` };
    if (active?.status === "OFFER_SELECTED") return { icon: "clock", title: "Waiting for payout", cta: "View loan", href: `/sme/loans/${active.id}` };
    if (active?.status === "PUBLISHED" && active.open_offers > 0) return { icon: "loan", title: `${active.open_offers} ${active.open_offers > 1 ? "offers" : "offer"} to compare`, cta: "Compare", href: `/sme/loans/${active.id}` };
    if (active?.status === "PUBLISHED") return { icon: "clock", title: "Waiting for offers", cta: "View request", href: `/sme/loans/${active.id}` };
    if (active?.status === "DRAFT") return { icon: "pencil", title: "Draft request", cta: "Continue", href: `/sme/loans/new?draft=${active.id}` };
    return { icon: "loan", title: "No loan request yet", cta: "Request a loan", href: "/sme/loans/new" };
  }, [apps.data, conns.data, latest]);

  return (
    <div className="stack-l">
      <PageHeader title={s.actingFor ? s.actingFor.name : s.org.name} />
      {loading ? <Skeleton h={160} r={16} /> : (
        <>
          <Card className="hstack spread wrap enter">
            <div className="hstack" style={{ gap: 16 }}><Tile name={next.icon} size="lg" /><span className="t-title">{next.title}</span></div>
            <Button href={next.href}>{next.cta}</Button>
          </Card>

          <div className="kpis">
            <Card className="kpi enter" style={{ "--i": 1 } as any}>
              <span className="l">Rating</span>
              <span className="v" style={{ color: latest ? CATEGORY[latest.category]?.color : undefined }}>{latest ? latest.category : "n/a"}</span>
              <div className="meter" style={{ marginTop: 6 }}><i style={{ width: `${latest?.score ?? 0}%` }} /></div>
              <span className="c">{latest ? `${latest.score} of 100 · ${CATEGORY[latest.category]?.word}${latest.source_type === "SYNTHETIC" ? " · demo data" : ""}` : ""}</span>
            </Card>
            <Card className="kpi enter" style={{ "--i": 2 } as any}>
              <span className="l">Fair rate range</span>
              <span className="v">{fmtRange(range)}</span>
              {range && <RangeBar range={range} />}
              <span className="c">Similar companies, illustrative</span>
            </Card>
          </div>

          <Section title="More">
            <List>
              <Row icon="sliders" title="Rating simulator" href="/sme/finances?tab=whatif" />
              <Row icon="shield" title="Privacy" href="/sme/privacy" />
              <Row icon="receipt" title="Fees" href="/sme/fees" />
            </List>
          </Section>
        </>
      )}
    </div>
  );
}

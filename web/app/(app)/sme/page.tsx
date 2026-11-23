"use client";
import { useMemo } from "react";
import { useApi } from "@/lib/client/api";
import { useSession } from "@/components/Providers";
import { Button, List, PageHeader, Row, Section, Skeleton } from "@/components/ui";
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
    const active = (apps.data ?? []).find((x) => ["FUNDED", "OFFER_SELECTED", "PUBLISHED", "DRAFT"].includes(x.status));
    if (!conns.data?.length) return { title: "Add your accounts", cta: "Add accounts", href: "/sme/finances?tab=data" };
    if (!latest) return { title: "Calculating your rating", cta: "View", href: "/sme/finances?tab=data" };
    if (active?.status === "FUNDED" && active.dispute_until && daysLeft(active.dispute_until) > 0) return { title: `Paid out · ${daysLeft(active.dispute_until)} days to report a problem`, cta: "View loan", href: `/sme/loans/${active.id}` };
    if (active?.status === "OFFER_SELECTED") return { title: "Waiting for payout", cta: "View loan", href: `/sme/loans/${active.id}` };
    if (active?.status === "PUBLISHED" && active.open_offers > 0) return { title: `${active.open_offers} ${active.open_offers > 1 ? "offers" : "offer"}`, cta: "Compare", href: `/sme/loans/${active.id}` };
    if (active?.status === "PUBLISHED") return { title: "Waiting for offers", cta: "View request", href: `/sme/loans/${active.id}` };
    if (active?.status === "DRAFT") return { title: "Draft request", cta: "Continue", href: `/sme/loans/new?draft=${active.id}` };
    return { title: "No loan request", cta: "Request a loan", href: "/sme/loans/new" };
  }, [apps.data, conns.data, latest]);

  return (
    <div className="stack-l">
      <PageHeader title={s.actingFor ? s.actingFor.name : s.org.name} />
      {loading ? <Skeleton h={120} r={6} /> : (
        <>
          <div className="hstack wrap" style={{ gap: 48 }}>
            <div className="stat"><span className="l">Rating</span><span className="v" style={{ fontSize: 44 }}>{latest ? latest.category : "n/a"}</span></div>
            <div className="stat"><span className="l">Score</span><span className="v" style={{ fontSize: 44 }}>{latest ? latest.score : "n/a"}<span className="muted" style={{ fontSize: 18 }}> / 100</span></span></div>
            <div className="stat"><span className="l">Fair rate</span><span className="v" style={{ fontSize: 44 }}>{fmtRange(range)}</span></div>
          </div>
          {latest && <div className="t-cap" style={{ marginTop: -24 }}>{CATEGORY[latest.category]?.word}{latest.source_type === "SYNTHETIC" ? " · demo data" : ""}</div>}

          <Section title="Next">
            <div className="hstack spread wrap" style={{ padding: "20px 0" }}>
              <span className="t-title">{next.title}</span>
              <Button href={next.href}>{next.cta}</Button>
            </div>
          </Section>

          <Section title="More">
            <List>
              <Row icon="sliders" title="What-if" href="/sme/finances?tab=whatif" />
              <Row icon="shield" title="Privacy" href="/sme/privacy" />
              <Row icon="receipt" title="Fees" href="/sme/fees" />
            </List>
          </Section>
        </>
      )}
    </div>
  );
}

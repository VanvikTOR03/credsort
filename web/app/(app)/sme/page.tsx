"use client";
import Link from "next/link";
import { useMemo } from "react";
import { useApi } from "@/lib/client/api";
import { useSession } from "@/components/Providers";
import { Button, Card, Meter, PageHeader, Ring, Row, List, Section, Skeleton, Pill } from "@/components/ui";
import { Icon, Tile } from "@/components/Icon";
import { CATEGORY } from "@/lib/labels";
import { chf, daysLeft } from "@/lib/format";

type Assess = { id: string; category: string; score: number; period_end: string; source_type: string };

export default function SmeHome() {
  const { session } = useSession();
  const first = (session!.actingFor ? session!.actingFor.name : session!.user.name.split(" ")[0]);
  const assess = useApi<Assess[]>("intelligence", "/v1/assessments");
  const conns = useApi<any[]>("accounting", "/v1/connections");
  const apps = useApi<any[]>("marketplace", "/v1/applications");
  const reqs = useApi<any[]>("marketplace", "/v1/access-requests");
  const latest = assess.data?.[0];
  const explain = useApi<any>("advisory", latest ? `/v1/assessments/${latest.id}/explanation` : null);
  const loading = assess.loading || conns.loading || apps.loading;

  const next = useMemo(() => {
    const a = apps.data ?? [];
    const active = a.find((x) => ["FUNDED", "OFFER_SELECTED", "PUBLISHED", "DRAFT"].includes(x.status));
    if (!conns.data?.length) return { icon: "plug", title: "Connect your accounting", text: "Link bexio or try demo data. It takes about a minute and nothing leaves your control.", cta: "Connect", href: "/sme/finances?tab=data" };
    if (!latest) return { icon: "gauge", title: "Calculating your score", text: "Your numbers are being checked. This usually takes a few seconds.", cta: "See progress", href: "/sme/finances?tab=data" };
    if (active?.status === "FUNDED" && active.dispute_until && daysLeft(active.dispute_until) > 0) return { icon: "calendar", title: "Did the money arrive?", text: `You can raise a problem for ${daysLeft(active.dispute_until)} more days.`, cta: "Review loan", href: `/sme/loans/${active.id}` };
    if (active?.status === "OFFER_SELECTED") return { icon: "clock", title: "Waiting for your lender", text: "Once they confirm the payout, your loan is complete.", cta: "View loan", href: `/sme/loans/${active.id}` };
    if (active?.status === "PUBLISHED" && active.open_offers > 0) return { icon: "loan", title: `${active.open_offers} offer${active.open_offers > 1 ? "s" : ""} to compare`, text: "Side by side, with the full cost of each.", cta: "Compare offers", href: `/sme/loans/${active.id}` };
    if (active?.status === "PUBLISHED") return { icon: "search", title: "Lenders are looking", text: "Your request is visible to matching lenders. We will tell you when an offer arrives.", cta: "View request", href: `/sme/loans/${active.id}` };
    if (active?.status === "DRAFT") return { icon: "pencil", title: "Finish your loan request", text: "A few more taps and lenders can start making offers.", cta: "Continue", href: `/sme/loans/${active.id}` };
    return { icon: "loan", title: "See what lenders would offer", text: "Ask for a loan. It is free, and you only pay if a loan is funded.", cta: "Start a request", href: "/sme/loans/new" };
  }, [apps.data, conns.data, latest]);

  const steps = useMemo(() => {
    const a = apps.data ?? [];
    const has = (s: string[]) => a.some((x) => s.includes(x.status));
    return [
      { label: "Connect accounting", done: !!conns.data?.length }, { label: "Check your score", done: !!latest },
      { label: "Ask for a loan", done: has(["PUBLISHED", "OFFER_SELECTED", "FUNDED", "DISPUTED", "CLOSED"]) }, { label: "Choose an offer", done: has(["OFFER_SELECTED", "FUNDED", "DISPUTED", "CLOSED"]) },
      { label: "Receive the money", done: has(["FUNDED", "CLOSED"]) },
    ];
  }, [apps.data, conns.data, latest]);
  const done = steps.filter((s) => s.done).length;
  const pending = reqs.data?.filter((r) => r.status === "PENDING").length ?? 0;

  return (
    <div className="stack-l">
      <PageHeader title={session!.actingFor ? first : `Hello, ${first}`} subtitle={session!.actingFor ? "Working on behalf of your client" : session!.org.name} />
      {loading ? <div className="stack"><Skeleton h={168} r={28} /><Skeleton h={140} r={20} /></div> : (
        <>
          <div className="hero enter">
            <div className="hstack" style={{ alignItems: "flex-start", gap: 16 }}>
              <Tile name={next.icon} color="orange" size="lg" />
              <div className="grow stack-s"><h2 className="t-title">{next.title}</h2><p className="t-foot">{next.text}</p></div>
            </div>
            <div style={{ marginTop: 18 }}><Button href={next.href}>{next.cta}<Icon name="arrow" /></Button></div>
          </div>

          <div className="grid c2">
            <Card lift className="enter" style={{ "--i": 1 } as any}>
              {latest ? (
                <Link href="/sme/finances" className="hstack" style={{ gap: 18, color: "inherit" }}>
                  <Ring value={latest.score} color={CATEGORY[latest.category]?.color} size={112} stroke={11}>
                    <div className="num" style={{ fontSize: 30, fontWeight: 750, letterSpacing: "-.03em", lineHeight: 1 }}>{latest.score}</div><div className="t-cap">of 100</div>
                  </Ring>
                  <div className="stack-s grow">
                    <div className="t-over">Credit health</div>
                    <div className="t-title">Category {latest.category} · {CATEGORY[latest.category]?.word}</div>
                    <div className="t-foot">Based on figures to {latest.period_end}{latest.source_type === "SYNTHETIC" ? " (demo data)" : ""}</div>
                  </div>
                </Link>
              ) : <div className="hstack"><Skeleton h={112} w={112} r={56} /><div className="grow stack-s"><Skeleton w="50%" /><Skeleton w="80%" h={12} /></div></div>}
            </Card>
            <Card className="enter stack" style={{ "--i": 2 } as any}>
              <div className="hstack spread"><div className="t-over">Get loan-ready</div><span className="t-foot num">{done} of {steps.length}</span></div>
              <Meter value={done} max={steps.length} label="Loan readiness" />
              <div className="stack-s">
                {steps.map((s) => (
                  <div className="hstack" key={s.label} style={{ gap: 10, opacity: s.done ? .55 : 1 }}>
                    <span className={`tile xs ${s.done ? "c-green" : "c-gray"}`} style={s.done ? undefined : { filter: "grayscale(1) opacity(.5)" }}><Icon name="check" /></span>
                    <span>{s.label}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {explain.data && (
            <Card className="enter stack-s" style={{ "--i": 3 } as any}>
              <div className="hstack"><Tile name="spark" color="purple" size="sm" /><div className="t-head">In plain words</div></div>
              <p>{explain.data.summary}</p>
              {explain.data.strengths?.[0] && <p className="muted">{explain.data.strengths[0]}</p>}
              <Link href="/sme/finances" className="t-foot" style={{ color: "var(--accent)", fontWeight: 600 }}>See the full breakdown</Link>
            </Card>
          )}

          <Section title="Shortcuts">
            <List>
              <Row icon="shield" color="indigo" title="Who can see my data" sub={pending ? `${pending} request${pending > 1 ? "s" : ""} waiting for you` : "You are in control"} href="/sme/privacy" value={pending ? <Pill tone="orange">{pending}</Pill> : undefined} />
              <Row icon="sliders" color="accent" title="Try a what-if" sub="See how a change would move your score" href="/sme/finances?tab=whatif" />
              <Row icon="receipt" color="green" title="Fees" sub="You pay only if a loan is funded" href="/sme/fees" />
            </List>
          </Section>
        </>
      )}
    </div>
  );
}

"use client";
import Link from "next/link";
import { useApi } from "@/lib/client/api";
import { Card, Empty, ListSkeleton, PageHeader, Pill, Button } from "@/components/ui";
import { Icon, Tile } from "@/components/Icon";
import { CATEGORY } from "@/lib/labels";
import { chf, pct, ago } from "@/lib/format";

export default function Matches() {
  const m = useApi<{ criteria_version: number; total: number; items: any[] }>("marketplace", "/v1/lender/matches", { refresh: 15000 });
  return (
    <div className="stack-l">
      <PageHeader title="Matches" subtitle={m.data ? `${m.data.total} compan${m.data.total === 1 ? "y fits" : "ies fit"} your criteria.` : "Companies that fit your criteria."} actions={<Button size="sm" variant="secondary" href="/lender/criteria" icon="sliders">Criteria</Button>} />
      {m.loading ? <ListSkeleton rows={3} /> : !m.data?.items.length ? (
        <Card><Empty icon="search" color="blue" title="No matches right now" text={m.data?.criteria_version === 0 ? "Set your criteria first, then matching companies show up here." : "New companies appear here as they publish. Widening your criteria may help."} action={<Button href="/lender/criteria">Edit criteria</Button>} /></Card>
      ) : (
        <div className="stack">{m.data.items.map((x, i) => {
          const f = x.fields, cat = f.assessment_category as string | undefined;
          return (
            <Link key={x.application_id} href={`/lender/apps/${x.application_id}`} style={{ color: "inherit" }}>
              <Card lift className="stack enter" style={{ "--i": i } as any}>
                <div className="hstack spread">
                  <div className="hstack"><span className="tile c-indigo"><span className="num" style={{ fontWeight: 800, fontSize: 18, position: "relative", zIndex: 1, textShadow: "0 1px 1px rgba(0,0,0,.25)" }}>{x.rank}</span></span>
                    <div><div className="t-head num">{chf(f.requested_amount)}</div><div className="t-foot">{f.term_months} months · {f.industry ?? "Industry hidden"}</div></div></div>
                  <div className="hstack" style={{ gap: 6 }}>{cat && <span className="pill" style={{ background: `color-mix(in srgb, ${CATEGORY[cat]?.color} 18%, transparent)`, color: "var(--label)" }}>Category {cat}</span>}{x.my_offer && <Pill tone="accent">Offer sent</Pill>}</div>
                </div>
                <div className="grid c3" style={{ gap: 8 }}>
                  {f.ebitda_margin && <div className="stat"><span className="v" style={{ fontSize: 20 }}>{pct(f.ebitda_margin)}</span><span className="l">EBITDA margin</span></div>}
                  {f.equity_ratio && <div className="stat"><span className="v" style={{ fontSize: 20 }}>{pct(f.equity_ratio)}</span><span className="l">Equity ratio</span></div>}
                  {f.debt_to_ebitda && <div className="stat"><span className="v" style={{ fontSize: 20 }}>{Number(f.debt_to_ebitda).toFixed(1)}×</span><span className="l">Debt / EBITDA</span></div>}
                </div>
                <div className="hstack spread t-foot"><span>{x.explanation.filter((e: any) => e.met).length} of {x.explanation.length} criteria met · published {ago(x.published_at)}</span><Icon name="chevron" className="chev" /></div>
              </Card>
            </Link>
          );
        })}</div>
      )}
    </div>
  );
}

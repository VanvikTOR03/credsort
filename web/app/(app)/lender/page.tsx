"use client";
import Link from "next/link";
import { useApi } from "@/lib/client/api";
import { Button, Card, Empty, ListSkeleton, PageHeader, Pill } from "@/components/ui";
import { chf, pct, ago } from "@/lib/format";

export default function Matches() {
  const m = useApi<{ criteria_version: number; total: number; items: any[] }>("marketplace", "/v1/lender/matches", { refresh: 15000 });
  return (
    <div>
      <PageHeader title="Matches" actions={<Button size="sm" variant="secondary" href="/lender/criteria">Criteria</Button>} />
      {m.loading ? <ListSkeleton rows={3} /> : !m.data?.items.length ? (
        <Empty icon="search" title="No matches" action={<Button href="/lender/criteria">Edit criteria</Button>} />
      ) : (
        <div className="offer-list">
          {m.data.items.map((x, i) => {
            const f = x.fields;
            return (
              <Link key={x.application_id} href={`/lender/apps/${x.application_id}`} style={{ display: "block" }}><Card lift className="offer enter" style={{ "--i": i, gridTemplateColumns: "minmax(0,2fr) repeat(3, minmax(0,1fr))" } as any}>
                <div>
                  <div className="t-head">{f.company_name ?? "Company"}</div>
                  <div className="t-foot">{f.industry} · {ago(x.published_at)}</div>
                </div>
                <div><div className="k">Request</div><div className="v">{chf(f.requested_amount, { compact: true })} · {Math.round(f.term_months / 12)}y</div></div>
                <div><div className="k">EBITDA margin</div><div className="v">{f.ebitda_margin ? pct(f.ebitda_margin) : "n/a"}</div></div>
                <div className="hstack" style={{ justifyContent: "space-between" }}><div><div className="k">Rating</div><div className="v">{f.assessment_category ?? "n/a"}</div></div>{x.my_offer && <Pill tone="accent">Offer sent</Pill>}</div>
              </Card></Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

import { NextRequest, NextResponse } from "next/server";
import { currentSession } from "@/lib/server/session";
import { issueContext } from "@/lib/server/identity";

/** A fiduciary starts (or ends, with null) acting on behalf of a client SME. The delegation is verified by Identity. */
export async function POST(req: NextRequest) {
  const s = await currentSession();
  if (!s) return NextResponse.json({ detail: "not signed in" }, { status: 401 });
  if (req.headers.get("x-csrf") !== s.csrf) return NextResponse.json({ detail: "bad csrf token" }, { status: 403 });
  const { sme_org_id, sme_name } = await req.json();
  const home = s.memberships?.find((m) => m.org_type === "FIDUCIARY")?.org_id ?? s.org?.id;
  try {
    await issueContext(s, home, sme_org_id ?? null);
    s.actingFor = sme_org_id ? { id: sme_org_id, name: sme_name ?? "client" } : null;
  } catch (e: any) {
    return NextResponse.json({ detail: e.message }, { status: e.status ?? 400 });
  }
  return NextResponse.json({ ok: true, org: s.org, actingFor: s.actingFor });
}

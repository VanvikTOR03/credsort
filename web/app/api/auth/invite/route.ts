import { NextRequest, NextResponse } from "next/server";
import { serviceUrl } from "@/lib/server/config";

/** Before sign-up: which fiduciary does an invitation code belong to? Returns the name only. */
export async function GET(req: NextRequest) {
  const code = (req.nextUrl.searchParams.get("code") ?? "").trim().toUpperCase();
  if (!/^[A-Z0-9-]{4,20}$/.test(code)) return NextResponse.json({ detail: "That code does not look right." }, { status: 422 });
  const r = await fetch(`${serviceUrl("identity")}/v1/public/referrals/${encodeURIComponent(code)}`, { cache: "no-store" }).catch(() => null);
  if (!r) return NextResponse.json({ detail: "Could not check the code right now." }, { status: 503 });
  if (!r.ok) return NextResponse.json({ detail: "We do not know this invitation code." }, { status: 404 });
  return NextResponse.json(await r.json());
}

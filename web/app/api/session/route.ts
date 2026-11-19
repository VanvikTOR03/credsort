import { NextResponse } from "next/server";
import { currentSession } from "@/lib/server/session";
import { freshContext } from "@/lib/server/identity";

export async function GET() {
  const s = await currentSession();
  if (!s) return NextResponse.json({ authenticated: false }, { status: 401 });
  try { await freshContext(s); } catch { return NextResponse.json({ authenticated: false }, { status: 401 }); }
  return NextResponse.json({
    authenticated: true, csrf: s.csrf, user: { email: s.email, name: s.name },
    org: s.org, memberships: s.memberships, actingFor: s.actingFor ?? null,
  });
}

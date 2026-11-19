import { NextRequest, NextResponse } from "next/server";
import { AUTH_MODE, COOKIE_NAME } from "@/lib/server/config";
import { createSession, cookieOptions } from "@/lib/server/session";
import { issueContext, whoAmI } from "@/lib/server/identity";

/** Development sign-in (AUTH_MODE=dev): choose a seeded demo account. No password exists or is asked for. */
export async function POST(req: NextRequest) {
  if (AUTH_MODE !== "dev") return NextResponse.json({ detail: "dev login is disabled" }, { status: 403 });
  const { email, name } = await req.json();
  if (typeof email !== "string" || !email.endsWith(".demo")) return NextResponse.json({ detail: "only demo accounts can use the dev login" }, { status: 400 });
  const s = createSession(email, typeof name === "string" ? name : email);
  try {
    const me = await whoAmI(s);
    if (me.memberships.length === 0) return NextResponse.json({ detail: "this demo account does not exist yet" }, { status: 404 });
    await issueContext(s, null, null);
  } catch (e: any) {
    return NextResponse.json({ detail: e.message ?? "could not sign in" }, { status: e.status ?? 502 });
  }
  const res = NextResponse.json({ org: s.org });
  res.cookies.set(COOKIE_NAME, s.id, cookieOptions());
  return res;
}

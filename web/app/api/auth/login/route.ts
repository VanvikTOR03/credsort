import { NextRequest, NextResponse } from "next/server";
import { AUTH_MODE, COOKIE_NAME, serviceUrl } from "@/lib/server/config";
import { createSession, cookieOptions } from "@/lib/server/session";
import { issueContext, whoAmI } from "@/lib/server/identity";

/**
 * Password sign-in. Identity checks the password (salted hash, lockout after repeated failures); this route only starts the server-side session.
 * Development (AUTH_MODE=dev) uses these local passwords; production signs in through Keycloak (ADR-0016).
 */
export async function POST(req: NextRequest) {
  if (AUTH_MODE !== "dev") return NextResponse.json({ detail: "Sign-in runs through single sign-on in this environment." }, { status: 501 });
  const b = await req.json().catch(() => ({}));
  if (typeof b.email !== "string" || typeof b.password !== "string" || !b.email || !b.password) return NextResponse.json({ detail: "Enter your email and password." }, { status: 422 });
  const r = await fetch(`${serviceUrl("identity")}/v1/auth/login`, {
    method: "POST", cache: "no-store", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: b.email, password: b.password }),
  }).catch(() => null);
  if (!r) return NextResponse.json({ detail: "Sign-in is temporarily unavailable." }, { status: 503 });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) return NextResponse.json({ detail: j.detail ?? "Could not sign in.", code: j.code }, { status: r.status });
  const s = createSession(j.email, j.name);
  try {
    const me = await whoAmI(s);
    if (me.memberships.length === 0) return NextResponse.json({ detail: "This account has no organization yet." }, { status: 404 });
    await issueContext(s, null, null);
  } catch (e: any) {
    return NextResponse.json({ detail: e.message ?? "Could not sign in." }, { status: e.status ?? 502 });
  }
  const res = NextResponse.json({ org: s.org });
  res.cookies.set(COOKIE_NAME, s.id, cookieOptions());
  return res;
}

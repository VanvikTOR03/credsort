import { NextRequest, NextResponse } from "next/server";
import { AUTH_MODE, COOKIE_NAME, serviceUrl } from "@/lib/server/config";
import { createSession, cookieOptions } from "@/lib/server/session";
import { issueContext, mintDevUserToken } from "@/lib/server/identity";

/**
 * Sign-up for a company, a lender or an accountant (fiduciary). Development (AUTH_MODE=dev): Identity stores a salted password hash.
 * Production signs users up in Keycloak first (ADR-0016); this route then only creates the organization.
 */
export async function POST(req: NextRequest) {
  if (AUTH_MODE !== "dev") return NextResponse.json({ detail: "Sign-up runs through single sign-on in this environment." }, { status: 501 });
  const b = await req.json();
  const email = String(b.email ?? "").trim().toLowerCase(), name = String(b.name ?? "").trim();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return NextResponse.json({ detail: "Enter a valid business email." }, { status: 422 });
  if (name.length < 2) return NextResponse.json({ detail: "Enter your first and last name." }, { status: 422 });
  if (b.terms !== true) return NextResponse.json({ detail: "Please accept the terms and the privacy policy." }, { status: 422 });
  const password = String(b.password ?? "");
  if (password.length < 10) return NextResponse.json({ detail: "Use a password with at least 10 characters." }, { status: 422 });
  const type = ["SME", "LENDER", "FIDUCIARY"].includes(b.type) ? b.type : "SME";
  const s = createSession(email, name);
  const body = {
    type, password, legal_name: b.legal_name, uid: b.uid || null, legal_form: b.legal_form || null, industry: b.industry || null,
    employees: typeof b.employees === "number" ? b.employees : null, canton: b.canton || null, referral_code: type === "SME" ? b.referral_code || null : null,
  };
  const r = await fetch(`${serviceUrl("identity")}/v1/organizations`, {
    method: "POST", cache: "no-store", headers: { authorization: `Bearer ${mintDevUserToken(email, name)}`, "content-type": "application/json" }, body: JSON.stringify(body),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    const detail = Array.isArray(j.errors) ? j.errors.map((e: any) => `${(e.loc ?? []).slice(-1)[0]}: ${e.msg}`).join("; ") : j.detail;
    return NextResponse.json({ detail: detail || "Could not create the account.", code: j.code }, { status: r.status });
  }
  try { await issueContext(s, null, null); } catch (e: any) { return NextResponse.json({ detail: e.message }, { status: e.status ?? 502 }); }
  const res = NextResponse.json({ org: s.org, type });
  res.cookies.set(COOKIE_NAME, s.id, cookieOptions());
  return res;
}

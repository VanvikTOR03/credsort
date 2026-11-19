import { createHmac } from "node:crypto";
import { DEV_USER_TOKEN_SECRET, AUTH_MODE, serviceUrl } from "./config";
import type { Session, OrgInfo, Membership } from "./session";

function b64(o: object) { return Buffer.from(JSON.stringify(o)).toString("base64url"); }

/** Development login only: a signed token standing in for Keycloak's access token. Refused by Identity when CREDSORT_ENV=prod. */
export function mintDevUserToken(email: string, name: string): string {
  const now = Math.floor(Date.now() / 1000);
  const head = b64({ alg: "HS256", typ: "JWT" });
  const body = b64({ sub: `dev:${email}`, email, name, aud: "credsort-identity-dev", iat: now, exp: now + 3600 });
  const sig = createHmac("sha256", DEV_USER_TOKEN_SECRET).update(`${head}.${body}`).digest("base64url");
  return `${head}.${body}.${sig}`;
}

export function jwtExp(token: string): number {
  try { return JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString()).exp * 1000; } catch { return 0; }
}

async function userToken(s: Session): Promise<string> {
  if (AUTH_MODE === "dev") return mintDevUserToken(s.email, s.name);
  if (s.userToken && (s.userTokenExp ?? 0) - Date.now() > 15_000) return s.userToken;
  throw new Error("session expired"); // Keycloak refresh-token grant is wired in lib/server/oidc.ts (unverified against a live Keycloak)
}

export async function whoAmI(s: Session): Promise<{ user: unknown; memberships: Membership[] }> {
  const r = await fetch(`${serviceUrl("identity")}/v1/me`, { headers: { authorization: `Bearer ${await userToken(s)}` }, cache: "no-store" });
  const j = await r.json();
  return { user: j.user, memberships: j.memberships ?? [] };
}

/** Exchanges the user's login for a short-lived context token (about 2 minutes) for one organization. */
export async function issueContext(s: Session, orgId?: string | null, onBehalfOf?: string | null): Promise<void> {
  const r = await fetch(`${serviceUrl("identity")}/v1/context-tokens`, {
    method: "POST", cache: "no-store",
    headers: { authorization: `Bearer ${await userToken(s)}`, "content-type": "application/json" },
    body: JSON.stringify({ org_id: orgId ?? null, on_behalf_of: onBehalfOf ?? null }),
  });
  const j = await r.json();
  if (!r.ok) throw Object.assign(new Error(j.detail || "sign-in failed"), { status: r.status, code: j.code });
  s.contextToken = j.token;
  s.contextExp = jwtExp(j.token);
  s.org = j.org as OrgInfo;
  s.memberships = j.memberships;
}

export async function freshContext(s: Session): Promise<string> {
  if (!s.contextToken || (s.contextExp ?? 0) - Date.now() < 20_000) await issueContext(s, s.org?.id, s.org?.on_behalf_of ?? null);
  return s.contextToken!;
}

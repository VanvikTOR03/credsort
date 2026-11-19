import { randomBytes } from "node:crypto";
import { cookies } from "next/headers";
import { AUTH_MODE, COOKIE_NAME } from "./config";

// Server-side sessions (ADR-0018): the browser only holds an opaque, HttpOnly cookie.
// This in-memory store is for development; production uses a small encrypted session database (docs/architecture/08 §3).
export type OrgInfo = { id: string; name: string; type: string; role: string; kyb_status: string; on_behalf_of?: string | null; scopes?: string[] };
export type Membership = { org_id: string; org_name: string; org_type: string; role: string };
export type Session = {
  id: string; email: string; name: string;
  userToken?: string; refreshToken?: string; userTokenExp?: number;
  contextToken?: string; contextExp?: number; org?: OrgInfo; memberships?: Membership[];
  actingFor?: { id: string; name: string } | null;
  csrf: string; created: number;
};

const g = globalThis as unknown as { __csSessions?: Map<string, Session> };
const store = (g.__csSessions ??= new Map());
const MAX_AGE_MS = 8 * 3600 * 1000;

export function createSession(email: string, name: string): Session {
  const id = randomBytes(32).toString("base64url");
  const s: Session = { id, email, name, csrf: randomBytes(16).toString("base64url"), created: Date.now() };
  store.set(id, s);
  return s;
}

export async function currentSession(): Promise<Session | null> {
  const id = cookies().get(COOKIE_NAME)?.value;
  if (!id) return null;
  const s = store.get(id);
  if (!s) return null;
  if (Date.now() - s.created > MAX_AGE_MS) { store.delete(id); return null; }
  return s;
}

export function destroySession(id: string) { store.delete(id); }

export function cookieOptions() {
  return { httpOnly: true, sameSite: "lax" as const, secure: AUTH_MODE !== "dev", path: "/", maxAge: MAX_AGE_MS / 1000 };
}

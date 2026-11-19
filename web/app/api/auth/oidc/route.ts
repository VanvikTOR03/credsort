import { NextResponse } from "next/server";
import { AUTH_MODE } from "@/lib/server/config";

/**
 * Keycloak OIDC (authorization code + PKCE) is the production sign-in (ADR-0016).
 * Not implemented in this build: it needs a running Keycloak, which could not be exercised here.
 * Docker Compose provides the realm skeleton in deploy/keycloak/realm.json.
 */
export async function GET() {
  return NextResponse.json({ detail: AUTH_MODE === "keycloak" ? "OIDC sign-in is not wired yet in this build" : "dev login is active" }, { status: 501 });
}

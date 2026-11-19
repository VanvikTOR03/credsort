import { NextRequest, NextResponse } from "next/server";
import { serviceUrl } from "@/lib/server/config";
import { currentSession } from "@/lib/server/session";
import { freshContext } from "@/lib/server/identity";

// The BFF: the browser never sees tokens and can never reach /internal endpoints or an unknown service.
async function proxy(req: NextRequest, { params }: { params: { service: string; path: string[] } }) {
  const base = serviceUrl(params.service);
  const path = "/" + params.path.join("/");
  if (!base || !path.startsWith("/v1/") || path.includes("..")) return NextResponse.json({ detail: "not found" }, { status: 404 });
  const s = await currentSession();
  if (!s) return NextResponse.json({ detail: "not signed in" }, { status: 401 });
  const mutating = req.method !== "GET" && req.method !== "HEAD";
  if (mutating && req.headers.get("x-csrf") !== s.csrf) return NextResponse.json({ detail: "bad csrf token" }, { status: 403 });
  let token: string;
  try { token = await freshContext(s); } catch { return NextResponse.json({ detail: "session expired" }, { status: 401 }); }
  const headers: Record<string, string> = { authorization: `Bearer ${token}` };
  for (const h of ["content-type", "idempotency-key", "accept-language"]) { const v = req.headers.get(h); if (v) headers[h] = v; }
  const url = base + path + req.nextUrl.search;
  try {
    const r = await fetch(url, { method: req.method, headers, body: mutating ? await req.text() : undefined, cache: "no-store" });
    const text = await r.text();
    return new NextResponse(text || null, { status: r.status, headers: { "content-type": r.headers.get("content-type") ?? "application/json" } });
  } catch {
    return NextResponse.json({ type: "about:blank", title: "Service unavailable", status: 503, code: "upstream_unavailable", detail: "That part of CredSort is not responding. Please try again in a moment." }, { status: 503 });
  }
}
export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };

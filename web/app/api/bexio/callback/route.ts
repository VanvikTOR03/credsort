import { NextRequest, NextResponse } from "next/server";
import { serviceUrl } from "@/lib/server/config";
import { currentSession } from "@/lib/server/session";
import { freshContext } from "@/lib/server/identity";

// bexio redirects the browser here after consent (UNVERIFIED against the bexio sandbox). The code never reaches page JavaScript.
export async function GET(req: NextRequest) {
  const s = await currentSession();
  const code = req.nextUrl.searchParams.get("code"), state = req.nextUrl.searchParams.get("state");
  const back = (q: string) => NextResponse.redirect(new URL(`/sme/finances?tab=data&${q}`, req.url));
  if (!s || !code || !state) return back("bexio=failed");
  const token = await freshContext(s);
  const r = await fetch(`${serviceUrl("accounting")}/v1/connections/bexio/callback`, {
    method: "POST", cache: "no-store", headers: { authorization: `Bearer ${token}`, "content-type": "application/json" }, body: JSON.stringify({ code, state }),
  });
  return back(r.ok ? "bexio=connected" : "bexio=failed");
}

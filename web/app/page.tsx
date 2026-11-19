import { redirect } from "next/navigation";
import { currentSession } from "@/lib/server/session";

const HOME: Record<string, string> = { SME: "/sme", LENDER: "/lender", PLATFORM: "/admin", FIDUCIARY: "/fiduciary" };
export const dynamic = "force-dynamic";
export default async function Index() {
  const s = await currentSession();
  redirect(s?.org ? (s.actingFor ? "/sme" : HOME[s.org.type] ?? "/login") : "/login");
}

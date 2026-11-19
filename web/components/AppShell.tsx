"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React from "react";
import { Icon, Tile } from "./Icon";
import { useSession, useToast } from "./Providers";
import { api, invalidate, useApi } from "@/lib/client/api";
import { Button, Pill } from "./ui";

type NavItem = { href: string; label: string; icon: string; color: string };
const NAV: Record<string, NavItem[]> = {
  SME: [
    { href: "/sme", label: "Home", icon: "home", color: "blue" },
    { href: "/sme/finances", label: "Finances", icon: "chart", color: "accent" },
    { href: "/sme/loans", label: "Loans", icon: "loan", color: "orange" },
    { href: "/sme/privacy", label: "Privacy", icon: "shield", color: "indigo" },
    { href: "/sme/more", label: "More", icon: "more", color: "gray" },
  ],
  LENDER: [
    { href: "/lender", label: "Matches", icon: "search", color: "blue" },
    { href: "/lender/offers", label: "Offers", icon: "loan", color: "orange" },
    { href: "/lender/criteria", label: "Criteria", icon: "sliders", color: "indigo" },
    { href: "/lender/more", label: "More", icon: "more", color: "gray" },
  ],
  PLATFORM: [
    { href: "/admin", label: "Review", icon: "shield", color: "blue" },
    { href: "/admin/pricing", label: "Pricing", icon: "franc", color: "orange" },
    { href: "/admin/charges", label: "Charges", icon: "receipt", color: "green" },
    { href: "/admin/more", label: "More", icon: "more", color: "gray" },
  ],
  FIDUCIARY: [
    { href: "/fiduciary", label: "Clients", icon: "people", color: "blue" },
    { href: "/fiduciary/more", label: "More", icon: "more", color: "gray" },
  ],
};
const HOME: Record<string, string> = { SME: "/sme", LENDER: "/lender", PLATFORM: "/admin", FIDUCIARY: "/fiduciary" };
export const homeFor = (type: string) => HOME[type] ?? "/login";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { session, reload } = useSession();
  const path = usePathname();
  const router = useRouter();
  const toast = useToast();
  const s = session!;
  const acting = s.actingFor;
  const kind = acting ? "SME" : s.org.type;
  const nav = NAV[kind] ?? NAV.SME;
  const unread = useApi<{ unread: number }>("notification", "/v1/notifications", { refresh: 20000 });
  const active = (i: NavItem) => (i.href === HOME[kind] ? path === i.href : path.startsWith(i.href));

  async function signOut() { await fetch("/api/auth/logout", { method: "POST" }); location.href = "/login"; }
  async function stopActing() {
    await fetch("/api/session/act-for", { method: "POST", headers: { "content-type": "application/json", "x-csrf": s.csrf }, body: JSON.stringify({ sme_org_id: null }) });
    invalidate(); await reload(); router.push("/fiduciary"); toast("Back to your clients");
  }
  const bell = (
    <Link href="/notifications" className="btn icon" aria-label={`Notifications${unread.data?.unread ? `, ${unread.data.unread} unread` : ""}`}>
      <Icon name="bell" />{!!unread.data?.unread && <span className="bell-dot">{unread.data.unread > 9 ? "9+" : unread.data.unread}</span>}
    </Link>
  );

  return (
    <div className="shell">
      <aside className="side" aria-label="Main">
        <div className="brand"><Tile name="franc" color="accent" size="sm" /> CredSort</div>
        {nav.map((i) => (
          <Link key={i.href} href={i.href} className="side-link" aria-current={active(i) ? "page" : undefined}><Tile name={i.icon} color={i.color} size="sm" />{i.label}</Link>
        ))}
        <Link href="/notifications" className="side-link" aria-current={path === "/notifications" ? "page" : undefined}><Tile name="bell" color="red" size="sm" />Notifications{!!unread.data?.unread && <Pill tone="red">{unread.data.unread}</Pill>}</Link>
        <div className="side-foot stack-s">
          <div className="hstack"><Tile name={s.org.type === "LENDER" ? "bank" : s.org.type === "SME" ? "building" : "user"} color="gray" size="sm" /><div className="grow" style={{ minWidth: 0 }}><div className="t-head" style={{ fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.org.name}</div><div className="t-cap">{s.user.name}</div></div></div>
          <Button variant="secondary" size="sm" block onClick={signOut}>Sign out</Button>
        </div>
      </aside>
      <main className="main">
        <div style={{ position: "fixed", top: 7, right: 16, zIndex: 45 }}>{bell}</div>
        {acting && (
          <div className="page" style={{ paddingBottom: 0, paddingTop: 56 }}>
            <div className="banner acting enter"><Tile name="people" color="indigo" size="sm" /><div className="grow"><b>Acting for {acting.name}</b><div className="t-cap">Everything you do is recorded under both organizations.</div></div><Button size="sm" variant="secondary" onClick={stopActing}>Stop</Button></div>
          </div>
        )}
        <div className="page page-in" key={path}>{children}</div>
      </main>
      <nav className="tabbar" aria-label="Main">
        {nav.map((i) => <Link key={i.href} href={i.href} className="tab" aria-current={active(i) ? "page" : undefined}><Icon name={i.icon} />{i.label}</Link>)}
      </nav>
    </div>
  );
}

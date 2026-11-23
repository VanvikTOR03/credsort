"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React, { useEffect, useRef, useState } from "react";
import { Icon, Logo, Tile } from "./Icon";
import { useSession, useToast } from "./Providers";
import { invalidate, useApi } from "@/lib/client/api";
import { Button } from "./ui";
import { Assistant } from "./Assistant";

type NavItem = { href: string; label: string; icon: string };
const NAV: Record<string, NavItem[]> = {
  SME: [
    { href: "/sme", label: "Home", icon: "home" },
    { href: "/sme/finances", label: "Finances", icon: "chart" },
    { href: "/sme/loans", label: "Loans", icon: "loan" },
    { href: "/sme/privacy", label: "Privacy", icon: "shield" },
  ],
  LENDER: [
    { href: "/lender", label: "Matches", icon: "search" },
    { href: "/lender/offers", label: "Offers", icon: "loan" },
    { href: "/lender/criteria", label: "Criteria", icon: "sliders" },
  ],
  PLATFORM: [
    { href: "/admin", label: "Review", icon: "shield" },
    { href: "/admin/pricing", label: "Pricing", icon: "franc" },
    { href: "/admin/charges", label: "Charges", icon: "receipt" },
  ],
  FIDUCIARY: [{ href: "/fiduciary", label: "Clients", icon: "people" }],
};
const HOME: Record<string, string> = { SME: "/sme", LENDER: "/lender", PLATFORM: "/admin", FIDUCIARY: "/fiduciary" };
export const homeFor = (type: string) => HOME[type] ?? "/login";
const initials = (n: string) => n.split(/\s+/).map((x) => x[0]).slice(0, 2).join("").toUpperCase();

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
  const [menu, setMenu] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const first = path === "/sme/loans/new" && typeof window !== "undefined" && new URLSearchParams(window.location.search).get("first") === "1";
  const active = (i: NavItem) => (i.href === HOME[kind] ? path === i.href : path.startsWith(i.href));
  useEffect(() => { setMenu(false); }, [path]);
  useEffect(() => {
    const off = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setMenu(false); };
    document.addEventListener("mousedown", off); return () => document.removeEventListener("mousedown", off);
  }, []);

  async function signOut() { await fetch("/api/auth/logout", { method: "POST" }); location.href = "/login"; }
  async function stopActing() {
    await fetch("/api/session/act-for", { method: "POST", headers: { "content-type": "application/json", "x-csrf": s.csrf }, body: JSON.stringify({ sme_org_id: null }) });
    invalidate(); await reload(); router.push("/fiduciary"); toast("Back to your clients");
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="container">
          <Logo />
          {!first && <nav className="topnav" aria-label="Main">{nav.map((i) => <Link key={i.href} href={i.href} aria-current={active(i) ? "page" : undefined}>{i.label}</Link>)}</nav>}
          {first && <span className="topright t-foot">2 / 3</span>}
          {!first && (
            <div className="topright" ref={box}>
              <Link href="/notifications" className="btn icon" aria-label={`Notifications${unread.data?.unread ? `, ${unread.data.unread} unread` : ""}`}>
                <Icon name="bell" />{!!unread.data?.unread && <span className="bell-dot">{unread.data.unread > 9 ? "9+" : unread.data.unread}</span>}
              </Link>
              <div className="menu-wrap">
                <button className="avatar-btn" onClick={() => setMenu(!menu)} aria-label="Account" aria-expanded={menu}>{initials(s.user.name)}</button>
                {menu && (
                  <div className="menu" role="menu">
                    <div><div className="t-head">{s.user.name}</div><div className="t-foot">{s.org.name}</div></div>
                    <hr className="sep" />
                    <Link href={`${HOME[kind]}/more`} role="menuitem">Settings</Link>
                    <Button size="sm" variant="secondary" onClick={signOut}>Sign out</Button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </header>
      {s.org.kyb_status === "PENDING" && !first && (
        <div className="container" style={{ paddingTop: 16 }}><div className="banner"><Tile name="warning" tone="warn" size="sm" />Your organization is being verified. Some actions unlock afterwards.</div></div>
      )}
      {acting && !first && (
        <div className="container" style={{ paddingTop: 16 }}>
          <div className="banner"><div className="grow" style={{ flex: 1 }}>Acting for <b>{acting.name}</b></div><Button size="sm" variant="secondary" onClick={stopActing}>Stop</Button></div>
        </div>
      )}
      <main className="page page-in" key={path}>{children}</main>
      {kind === "SME" && !first && <Assistant />}
      {!first && (
        <nav className="tabbar" aria-label="Main">
          {nav.map((i) => <Link key={i.href} href={i.href} className="tab" aria-current={active(i) ? "page" : undefined}><Icon name={i.icon} />{i.label}</Link>)}
        </nav>
      )}
    </div>
  );
}

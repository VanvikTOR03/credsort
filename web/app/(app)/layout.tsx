"use client";
import { AppShell } from "@/components/AppShell";
import { SessionProvider, ToastProvider } from "@/components/Providers";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <ToastProvider><SessionProvider><AppShell>{children}</AppShell></SessionProvider></ToastProvider>;
}

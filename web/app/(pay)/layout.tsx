"use client";
import { SessionProvider, ToastProvider } from "@/components/Providers";

// The checkout runs in its own window: no navigation, just the payment.
export default function PayLayout({ children }: { children: React.ReactNode }) {
  return <ToastProvider><SessionProvider>{children}</SessionProvider></ToastProvider>;
}

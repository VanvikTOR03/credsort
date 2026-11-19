import "./globals.css";
import type { Metadata, Viewport } from "next";

export const metadata: Metadata = { title: "CredSort", description: "One profile. Many lenders. Your best rate." };
export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover", themeColor: [{ media: "(prefers-color-scheme: light)", color: "#f2f2f7" }, { media: "(prefers-color-scheme: dark)", color: "#000000" }] };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}

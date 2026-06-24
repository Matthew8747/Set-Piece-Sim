import type { Metadata } from "next";
import { Bricolage_Grotesque, Hanken_Grotesk, IBM_Plex_Mono } from "next/font/google";
import type { ReactNode } from "react";

import { AppNav } from "@/components/shell/AppNav";
import { PageTransition } from "@/components/shell/PageTransition";

import "./globals.css";

// Type system (doc 07): a characterful editorial grotesque for display, a clean
// humanist grotesque for body, IBM Plex Mono for ALL numerals (tabular). Loaded
// here as CSS variables; tokens.css wires them into --font-display/-sans/-mono.
const display = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-bricolage",
  display: "swap",
});
const sans = Hanken_Grotesk({
  subsets: ["latin"],
  variable: "--font-hanken",
  display: "swap",
});
const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Restart Lab · set-piece intelligence",
  description:
    "AI-assisted set-piece optimization for international football. Physics simulation, Monte Carlo experimentation, and machine-learning routine search for the 2026 World Cup.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <body className="min-h-screen antialiased">
        <div className="flex min-h-screen flex-col md:flex-row">
          <AppNav />
          <main className="relative flex-1 overflow-x-hidden">
            <PageTransition>{children}</PageTransition>
          </main>
        </div>
      </body>
    </html>
  );
}

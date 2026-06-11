import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Restart Lab",
  description:
    "AI-assisted set-piece optimization for international football. Physics simulation, Monte Carlo experimentation, and machine-learning routine search for the 2026 World Cup.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}

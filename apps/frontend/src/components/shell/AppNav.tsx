"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { EnvironmentBadge } from "@/components/EnvironmentBadge";

// Persistent app chrome (doc 07: one console, not a set of loose pages). A slim
// rail on desktop, a top bar on small screens. Active state is derived from the
// pathname so the analyst always knows where they are.

type NavItem = {
  href: string;
  label: string;
  hint: string;
  icon: ReactNode;
};

const ITEMS: NavItem[] = [
  {
    href: "/scenarios",
    label: "Scenarios",
    hint: "Build · simulate · replay",
    icon: (
      // corner-arc + ball: the workbench
      <svg viewBox="0 0 24 24" fill="none" aria-hidden className="size-[18px]">
        <path d="M4 4v16h16" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M4 9a11 11 0 0 1 11 11" stroke="currentColor" strokeWidth="1.6" opacity="0.5" />
        <circle cx="15.5" cy="8.5" r="2.4" stroke="currentColor" strokeWidth="1.6" />
      </svg>
    ),
  },
  {
    href: "/optimize",
    label: "Optimization",
    hint: "Search · convergence · lineage",
    icon: (
      // rising search trace
      <svg viewBox="0 0 24 24" fill="none" aria-hidden className="size-[18px]">
        <path
          d="M4 18c3-1 4-9 8-9s2 5 4 5 3-6 4-7"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="20" cy="7" r="1.6" fill="currentColor" />
      </svg>
    ),
  },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppNav() {
  const pathname = usePathname() ?? "/";

  return (
    <nav
      aria-label="Primary"
      className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-2 border-b border-(--color-line)/10 bg-(--color-surface)/80 px-4 backdrop-blur-md md:h-screen md:w-60 md:flex-col md:items-stretch md:gap-1 md:border-r md:border-b-0 md:px-3 md:py-5"
    >
      <Link
        href="/"
        className="group flex items-center gap-2.5 rounded-lg px-2 py-1.5 md:mb-4"
        aria-label="Restart Lab home"
      >
        <span className="grid size-8 place-items-center rounded-md bg-(--color-signal)/12 ring-1 ring-(--color-signal)/25 transition group-hover:bg-(--color-signal)/20">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden className="size-[18px]">
            <circle cx="12" cy="12" r="8.5" stroke="var(--color-signal)" strokeWidth="1.6" />
            <path
              d="M12 3.5v17M3.5 12h17"
              stroke="var(--color-signal)"
              strokeWidth="1.2"
              opacity="0.5"
            />
          </svg>
        </span>
        <span className="flex flex-col leading-none">
          <span className="font-display text-[15px] font-semibold tracking-tight">Restart Lab</span>
          <span className="mt-0.5 hidden font-mono text-[10px] tracking-widest text-(--color-line-muted) uppercase md:block">
            set-piece intelligence
          </span>
        </span>
      </Link>

      <div className="flex items-center gap-1 md:flex-col md:items-stretch md:gap-1">
        {ITEMS.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                active
                  ? "bg-(--color-line)/[0.06] text-(--color-line)"
                  : "text-(--color-line-muted) hover:bg-(--color-line)/[0.04] hover:text-(--color-line)"
              }`}
            >
              <span
                aria-hidden
                className={`absolute left-0 top-1/2 h-0 w-[3px] -translate-y-1/2 rounded-r-full bg-(--color-signal) transition-all duration-300 ${
                  active ? "h-6 opacity-100" : "opacity-0 group-hover:h-3 group-hover:opacity-40"
                }`}
              />
              <span className={active ? "text-(--color-signal)" : "text-current"}>{item.icon}</span>
              <span className="flex flex-col">
                <span className="font-medium">{item.label}</span>
                <span className="hidden text-[11px] text-(--color-line-muted) md:block">
                  {item.hint}
                </span>
              </span>
            </Link>
          );
        })}
      </div>

      <div className="ml-auto flex items-center md:mt-auto md:ml-0">
        <EnvironmentBadge environment="dev" />
      </div>
    </nav>
  );
}
